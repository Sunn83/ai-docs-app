import os
import json
import hashlib
import subprocess
import re
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import fitz  # PyMuPDF

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "pdfs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")
CACHE_FILE = os.path.join(DATA_DIR, "cache_info.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150


# ---------------------------------------------------
# 🔹 Helper για πίνακες σε Markdown
# ---------------------------------------------------
def table_to_markdown(table, wrap_length=90):
    def wrap_text(text, max_length=wrap_length):
        words = text.split()
        lines, current = [], ""
        for word in words:
            if len(current) + len(word) + 1 > max_length:
                lines.append(current)
                current = word
            else:
                current += (" " if current else "") + word
        if current:
            lines.append(current)
        return " ".join(lines)

    rows_text = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip().replace("\u00A0", " ").replace("\r", "").replace("\n", " ")
            text = wrap_text(text)
            cells.append(text)
        rows_text.append(" | ".join(cells))

    if not rows_text:
        return ""

    num_cols = rows_text[0].count("|") + 1
    separator = " | ".join(["---"] * num_cols)
    return "\n".join(["", "📊 Πίνακας:", rows_text[0], separator, *rows_text[1:], ""])


# ---------------------------------------------------
# 🔹 Υπολογισμός hash για caching
# ---------------------------------------------------
def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------
# 🔹 Διαβάζει sections από DOCX
# ---------------------------------------------------
def read_docx_sections(filepath):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(filepath)
    sections, current_body = [], []
    current_title = None

    def get_paragraph_text_with_breaks(paragraph):
        parts = []
        for run in paragraph.runs:
            if run.text:
                parts.append(run.text)
            for _ in run._element.findall(".//w:br", namespaces=run._element.nsmap):
                parts.append("\n")
        return "".join(parts).replace("\u00A0", " ").replace("\r", "").strip()

    def flush_section():
        nonlocal current_title, current_body
        if not current_body:
            return
        text = "\n\n".join([t.strip() for t in current_body if t.strip()])
        if text:
            sections.append({"title": current_title.strip() if current_title else None, "text": text})
        current_title, current_body = None, []

    for child in doc.element.body:
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, doc)
            txt = get_paragraph_text_with_breaks(paragraph)
            if not txt:
                continue
            style = paragraph.style.name.lower() if paragraph.style else ""
            if style.startswith("heading") or re.match(r"^\s*(άρθρο|ενότητα|θέμα|\d+(\.\d+)+)", txt.lower()):
                flush_section()
                current_title = txt
                continue
            current_body.append(txt)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            current_body.append(table_to_markdown(table))

    flush_section()
    return sections or [{"title": None, "text": "\n".join(p.text for p in doc.paragraphs if p.text.strip())}]


# ---------------------------------------------------
# 🔹 Σπάσιμο σε chunks
# ---------------------------------------------------
def chunk_section_text(text, max_words=500, overlap_words=100):
    if not text:
        return []
    parts = re.split(r'(?=📊 Πίνακας:)', text)
    chunks = []
    prev_part = ""
    join_triggers = ["πίνακα", "πίνακας", "κάτωθι πίνακα", "παρακάτω πίνακα", "ακόλουθο πίνακα", "βλέπε πίνακα", "πίνακα:"]

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part.startswith("📊 Πίνακας:"):
            if prev_part and any(trig in prev_part.lower() for trig in join_triggers):
                chunks[-1] = chunks[-1].rstrip() + "\n\n" + part
                prev_part = ""
            else:
                chunks.append(part)
            continue

        sentences = re.split(r'(?<=[.!?])\s+', part)
        cur, cur_count = [], 0
        for s in sentences:
            wcount = len(s.split())
            if cur_count + wcount > max_words and cur:
                joined = " ".join(cur).strip()
                chunks.append(joined)
                tail = " ".join(" ".join(cur).split()[-overlap_words:])
                cur = [tail, s]
                cur_count = len(tail.split()) + wcount
            else:
                cur.append(s)
                cur_count += wcount
        if cur:
            joined = " ".join(cur).strip()
            chunks.append(joined)
            prev_part = joined

    return [c for c in chunks if len(c.split()) > 5]


# ---------------------------------------------------
# 🔹 Μετατροπή DOCX → PDF
# ---------------------------------------------------
def convert_to_pdf(docx_path, pdf_dir):
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_file = os.path.join(pdf_dir, Path(docx_path).stem + ".pdf")
    if not os.path.exists(pdf_file):
        print(f"⚙️ Μετατροπή σε PDF: {os.path.basename(docx_path)} ...")
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", pdf_dir, docx_path], check=True)
    return pdf_file


# ---------------------------------------------------
# 🔹 Βρίσκει σελίδα στο PDF
# ---------------------------------------------------
def get_page_for_text(pdf_path, text_snippet, cache):
    if pdf_path in cache:
        for snippet, page in cache[pdf_path].items():
            if snippet == text_snippet[:150]:
                return page
    try:
        doc = fitz.open(pdf_path)
        snippet = text_snippet[:150]
        for page_num, page in enumerate(doc, start=1):
            if snippet in page.get_text("text"):
                cache.setdefault(pdf_path, {})[snippet] = page_num
                return page_num
        return 1
    except Exception:
        return 1


# ---------------------------------------------------
# 🔹 Φόρτωση DOCX με caching
# ---------------------------------------------------
def load_docs(cache):
    metadata, all_chunks = [], []
    os.makedirs(DATA_DIR, exist_ok=True)
    doc_files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    print(f"🔎 Εντοπίστηκαν {len(doc_files)} αρχεία DOCX")

    cached_hashes = cache.get("file_hashes", {})
    new_hashes = {}

    for fname in doc_files:
        path = os.path.join(DOCS_PATH, fname)
        filehash = file_hash(path)
        new_hashes[fname] = filehash
        pdf_path = convert_to_pdf(path, PDF_PATH)

        # Skip αν δεν έχει αλλάξει
        if cached_hashes.get(fname) == filehash:
            print(f"⏩ Παράκαμψη (χωρίς αλλαγές): {fname}")
            continue

        print(f"📘 Επεξεργασία: {fname}")
        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            chunks = chunk_section_text(sec["text"], max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            for cj, chunk in enumerate(chunks):
                page = get_page_for_text(pdf_path, chunk, cache.get("page_cache", {}))
                metadata.append({
                    "filename": fname,
                    "pdf_path": pdf_path,
                    "section_title": sec.get("title"),
                    "section_idx": si,
                    "chunk_id": cj,
                    "page": page,
                    "text": chunk
                })
                all_chunks.append(chunk)

    cache["file_hashes"] = new_hashes
    return all_chunks, metadata, cache


# ---------------------------------------------------
# 🔹 Δημιουργία FAISS index
# ---------------------------------------------------
def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index


# ---------------------------------------------------
# 🔹 Main
# ---------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Πλήρες indexing όλων των αρχείων")
    args = parser.parse_args()

    cache = {}
    if os.path.exists(CACHE_FILE) and not args.rebuild:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    print("🔍 Εκκίνηση indexing...")
    chunks, metadata, cache = load_docs(cache)

    if not chunks:
        print("✅ Δεν υπάρχουν νέα ή τροποποιημένα αρχεία. Τίποτα προς ενημέρωση.")
        return

    print(f"➡️ {len(chunks)} νέα chunks προς επεξεργασία.")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")

    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    main()
