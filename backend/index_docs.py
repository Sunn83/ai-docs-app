import os
import json
import re
import subprocess
import argparse
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import fitz

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "pdfs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150


# ---------------------------------------------------
# 🔹 Helper: Πίνακες σε Markdown
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
            text = cell.text.strip()
            text = text.replace("\u00A0", " ").replace("\r", "").replace("\n", " ")
            text = wrap_text(text)
            cells.append(text)
        rows_text.append(" | ".join(cells))

    if not rows_text:
        return ""

    num_cols = rows_text[0].count("|") + 1
    separator = " | ".join(["---"] * num_cols)

    markdown_table = "\n".join([
        "",
        "📊 Πίνακας:",
        rows_text[0],
        separator,
        *rows_text[1:],
        ""
    ])
    return markdown_table


# ---------------------------------------------------
# 🔹 Διαβάζει sections από DOCX
# ---------------------------------------------------
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
            for br in run._element.findall(".//w:br", namespaces=run._element.nsmap):
                parts.append("\n")
        text = "".join(parts)
        text = text.replace("\u00A0", " ").replace("\r", "").strip()
        return text

    def flush_section():
        nonlocal current_title, current_body
        if not current_title and not current_body:
            return
        text = "\n\n".join([t.strip() for t in current_body if t.strip()])
        if text.strip():
            sections.append({
                "title": current_title.strip() if current_title else None,
                "text": text.strip()
            })
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
        all_text = "\n".join([get_paragraph_text_with_breaks(p) for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]
    return sections


# ---------------------------------------------------
# 🔹 Σπάσιμο σε chunks
# ---------------------------------------------------
def chunk_section_text(section_text, max_words=500, overlap_words=100):
    if not section_text:
        return []

    parts = re.split(r'(?=📊 Πίνακας:)', section_text)
    chunks = []
    prev_part = ""

    join_triggers = ["πίνακα", "πίνακας", "κάτωθι πίνακα", "παρακάτω πίνακα", "ακόλουθο πίνακα", "βλέπε πίνακα", "πίνακα:"]

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part.startswith("📊 Πίνακας:"):
            if prev_part and any(trig in prev_part.lower() for trig in join_triggers):
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


# ---------------------------------------------------
# 🔹 DOCX → PDF (LibreOffice)
# ---------------------------------------------------
def convert_to_pdf(docx_path, pdf_dir):
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_file = os.path.join(pdf_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")

    if not os.path.exists(pdf_file):
        print(f"⚙️ Μετατροπή σε PDF: {os.path.basename(docx_path)} ...")
        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", pdf_dir, docx_path
            ], check=True)
        except Exception as e:
            print(f"❌ Σφάλμα στη μετατροπή σε PDF: {e}")
    else:
        print(f"📄 Υπάρχει ήδη PDF για {os.path.basename(docx_path)}")

    return pdf_file


# ---------------------------------------------------
# 🔹 Εύρεση σελίδας για κομμάτι κειμένου
# ---------------------------------------------------
def get_page_for_text(pdf_path, text_snippet):
    try:
        doc = fitz.open(pdf_path)
        snippet = text_snippet[:1000]
        for page_num, page in enumerate(doc, start=1):
            if snippet[:40].strip() in page.get_text("text"):
                return page_num
        return 1
    except Exception as e:
        print(f"⚠️ Δεν βρέθηκε σελίδα για {os.path.basename(pdf_path)}: {e}")
        return 1


# ---------------------------------------------------
# 🔹 Διαβάζει DOCX & δημιουργεί metadata
# ---------------------------------------------------
def load_docs():
    metadata, all_chunks = [], []
    doc_files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    print(f"Συνολικά {len(doc_files)} αρχεία προς επεξεργασία.")

    for i, fname in enumerate(doc_files, start=1):
        print(f"📘 ({i}/{len(doc_files)}) Διαβάζω: {fname} ...")
        path = os.path.join(DOCS_PATH, fname)
        pdf_path = convert_to_pdf(path, PDF_PATH)

        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks and sec_text.strip():
                chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                page = get_page_for_text(pdf_path, chunk)
                metadata.append({
                    "filename": fname,
                    "pdf_path": pdf_path,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "page": page,
                    "text": chunk
                })
                all_chunks.append(chunk)
        print(f"✅ Ολοκληρώθηκε: {fname} ({len(sections)} ενότητες).")

    return all_chunks, metadata


# ---------------------------------------------------
# 🔹 FAISS βοηθητικά
# ---------------------------------------------------
def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


def rebuild_index(chunks, metadata):
    print("🧠 Δημιουργία ΝΕΟΥ index από την αρχή...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True).astype('float32')
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("✅ Νέο index δημιουργήθηκε επιτυχώς!")


def append_to_index(new_files, metadata):
    with open(META_FILE, "r", encoding="utf-8") as f:
        old_meta = json.load(f)
    index = faiss.read_index(INDEX_FILE)
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    new_meta = [m for m in metadata if m["filename"] in new_files]
    chunks = [m["text"] for m in new_meta]

    if not chunks:
        print("ℹ️ Δεν υπάρχουν νέα κομμάτια για προσθήκη.")
        return

    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True).astype('float32')
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    faiss.write_index(index, INDEX_FILE)

    merged_meta = old_meta + new_meta
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(merged_meta, f, ensure_ascii=False, indent=2)

    print(f"✅ Προστέθηκαν {len(new_meta)} νέα κομμάτια στο index.")


def remove_deleted_files(removed_files):
    """Αφαιρεί metadata για αρχεία που διαγράφηκαν."""
    if not removed_files:
        return
    print(f"🧹 Καθαρισμός index από {len(removed_files)} διαγραμμένα αρχεία...")
    with open(META_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    new_meta = [m for m in metadata if m["filename"] not in removed_files]
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(new_meta, f, ensure_ascii=False, indent=2)
    print("✅ Διαγράφηκαν από το meta.json.")
    print("⚠️ Το FAISS index δεν μπορεί να αφαιρέσει vectors — για πλήρη καθαρισμό, τρέξε με --rebuild.")


# ---------------------------------------------------
# 🔹 Main
# ---------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Κάνει ολικό rebuild του index")
    args = parser.parse_args()

    old_metadata = []
    if os.path.exists(META_FILE) and os.path.exists(INDEX_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            old_metadata = json.load(f)
        old_files = {m["filename"] for m in old_metadata}
    else:
        old_files = set()

    chunks, metadata = load_docs()
    current_files = {m["filename"] for m in metadata}
    new_files = current_files - old_files
    removed_files = old_files - current_files

    print(f"🆕 Νέα αρχεία: {len(new_files)}")
    print(f"🗑️  Διαγραμμένα αρχεία: {len(removed_files)}")

    if args.rebuild or not old_metadata:
        rebuild_index(chunks, metadata)
    else:
        if new_files:
            append_to_index(new_files, metadata)
        if removed_files:
            remove_deleted_files(removed_files)
        if not new_files and not removed_files:
            print("✅ Δεν υπάρχουν αλλαγές — το index είναι ενημερωμένο.")


if __name__ == "__main__":
    main()
