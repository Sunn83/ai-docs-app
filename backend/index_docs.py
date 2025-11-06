import os
import json
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re
from tqdm import tqdm  # για progress bar

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

# mapping DOCX → PDF link
PDF_MAP = {
    "φορολογια2025.docx": "https://mydomain.com/pdfs/φορολογια2025.pdf",
    "κληρονομιες.docx": "https://mydomain.com/pdfs/κληρονομιες.pdf"
}

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150


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
            text = cell.text.strip()
            text = text.replace("\u00A0", " ").replace("\r", "").replace("\n", " ")
            text = wrap_text(text)
            cells.append(text)
        rows_text.append(" | ".join(cells))

    if not rows_text:
        return ""

    num_cols = rows_text[0].count("|") + 1
    separator = " | ".join(["---"] * num_cols)

    return "\n".join(["", "📊 Πίνακας:", rows_text[0], separator, *rows_text[1:], ""])


def read_docx_sections(filepath):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(filepath)
    sections = []
    current_title = None
    current_body = []

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
        if not current_title and not current_body:
            return
        text = "\n\n".join([t.strip() for t in current_body if t.strip()])
        if text.strip():
            sections.append({"title": current_title.strip() if current_title else None, "text": text.strip()})
        current_title = None
        current_body = []

    for child in doc.element.body:
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, doc)
            txt = get_paragraph_text_with_breaks(paragraph)
            if not txt:
                continue
            style = ""
            try:
                style = paragraph.style.name.lower()
            except Exception:
                pass
            if style.startswith("heading") or "επικεφαλίδα" in style or re.match(r"^\s*(άρθρο|ενότητα|θέμα|\d+(\.\d+)+)", txt.lower()):
                flush_section()
                current_title = txt
                continue
            current_body.append(txt)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            table_md = table_to_markdown(table)
            if table_md.strip():
                current_body.append(table_md)

    flush_section()
    if not sections:
        all_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]
    return sections


def chunk_section_text(section_text, max_words=500, overlap_words=100):
    if not section_text:
        return []
    parts = re.split(r'(?=📊 Πίνακας:)', section_text)
    chunks, prev_part = [], ""
    join_triggers = ["πίνακα", "κάτωθι πίνακα", "βλέπε πίνακα", "παρακάτω πίνακα"]
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("📊 Πίνακας:"):
            if prev_part and any(t in prev_part.lower() for t in join_triggers):
                prev_part = prev_part.rstrip() + "\n\n" + part.strip()
                chunks[-1] = prev_part
                prev_part = ""
            else:
                chunks.append(part)
            continue
        sentences = re.split(r'(?<=[\.\!\?])\s+', part)
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
    chunks = [c for c in chunks if len(c.split()) > 5]
    return chunks


def load_docs():
    metadata, all_chunks = [], []
    print("🔍 Ανάλυση εγγράφων...")
    for fname in tqdm(os.listdir(DOCS_PATH)):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        total_words = 0
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks:
                chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                total_words += len(chunk.split())
                page_est = (total_words // 400) + 1
                metadata.append({
                    "filename": fname,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "page": page_est,
                    "pdf_url": PDF_MAP.get(fname),
                    "text": chunk
                })
                all_chunks.append(chunk)
    return all_chunks, metadata


def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index


def main(reset=False):
    if not reset and os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
        print("📦 Βρέθηκε υπάρχον index — ενημέρωση για νέες/διαγραμμένες εγγραφές.")
        with open(META_FILE, "r", encoding="utf-8") as f:
            old_meta = json.load(f)
        old_docs = {m["filename"] for m in old_meta}
    else:
        print("🧹 Νέα εκκίνηση (reset).")
        old_meta, old_docs = [], set()

    all_docs = {f for f in os.listdir(DOCS_PATH) if f.endswith(".docx")}
    to_remove = old_docs - all_docs
    to_add = all_docs - old_docs

    if to_remove:
        print(f"🗑️ Διαγραφή docx: {to_remove}")
        old_meta = [m for m in old_meta if m["filename"] not in to_remove]

    if to_add:
        print(f"➕ Νέα docx προς προσθήκη: {to_add}")
    else:
        print("✅ Δεν υπάρχουν νέα αρχεία προς προσθήκη.")

    chunks, metadata = load_docs()
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")
    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True).astype('float32')
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("✅ Ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    import sys
    reset_flag = "--reset" in sys.argv
    main(reset=reset_flag)
