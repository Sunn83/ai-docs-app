import os
import json
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re
import subprocess

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "pdfs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# ---------------------------------------------------
# 🔹 1. Helper για πίνακες σε Markdown
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
# 🔹 2. Διαβάζει sections από DOCX
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
# 🔹 3. Σπάσιμο κειμένου σε chunks
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
# 🔹 4. Μετατροπή DOCX → PDF (LibreOffice)
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
# 🔹 5. Φόρτωση όλων των DOCX
# ---------------------------------------------------
def load_docs():
    metadata, all_chunks = [], []
    doc_files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    total_files = len(doc_files)
    print(f"Συνολικά {total_files} αρχεία προς επεξεργασία.")

    for i, fname in enumerate(doc_files, start=1):
        print(f"📘 ({i}/{total_files}) Διαβάζω: {fname} ...")
        path = os.path.join(DOCS_PATH, fname)

        # ➕ Αυτόματη μετατροπή σε PDF (αν δεν υπάρχει)
        pdf_path = convert_to_pdf(path, PDF_PATH)

        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks and sec_text.strip():
                chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                metadata.append({
                    "filename": fname,
                    "pdf_path": pdf_path,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "text": chunk
                })
                all_chunks.append(chunk)
        print(f"✅ Ολοκληρώθηκε: {fname} ({len(sections)} ενότητες).")
    return all_chunks, metadata


# ---------------------------------------------------
# 🔹 6. Δημιουργία FAISS index
# ---------------------------------------------------
def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


# ---------------------------------------------------
# 🔹 7. Main
# ---------------------------------------------------
def main():
    chunks, metadata = load_docs()
    print(f"➡️  Βρέθηκαν {len(chunks)} chunks προς επεξεργασία.")
    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")
    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype('float32')
    print("🔧 Κανονικοποίηση embeddings (L2) + δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    main()
