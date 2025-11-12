import os
import json
import hashlib
import argparse
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re
import subprocess
import fitz
import time

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "pdfs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")
CACHE_FILE = os.path.join(DATA_DIR, "index_cache.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# -------------------- Helpers --------------------
def get_file_hash(filepath):
    h = hashlib.sha1()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def convert_to_pdf(docx_path, pdf_dir):
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_file = os.path.join(pdf_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
    if not os.path.exists(pdf_file):
        print(f"⚙️ Μετατροπή σε PDF: {os.path.basename(docx_path)} ...")
        try:
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", pdf_dir, docx_path],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"❌ Σφάλμα PDF: {e}")
    else:
        print(f"📄 Υπάρχει ήδη PDF για {os.path.basename(docx_path)}")
    return pdf_file

def read_docx_sections(filepath):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(filepath)
    sections, current_body = [], []
    current_title = None

    def flush():
        nonlocal current_body, current_title
        if current_body:
            text = "\n\n".join(current_body).strip()
            if text:
                sections.append({"title": current_title, "text": text})
        current_body, current_title = [], None

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            txt = p.text.strip()
            if not txt:
                continue
            style = p.style.name.lower() if p.style and p.style.name else ""
            if style.startswith("heading") or re.match(r"^\s*(άρθρο|ενότητα|θέμα|\d+(\.\d+)+)", txt.lower()):
                flush()
                current_title = txt
            else:
                current_body.append(txt)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
            if rows:
                current_body.append("\n".join(rows))
    flush()
    return sections

def chunk_text(text, max_words=500, overlap=100):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_words]
        chunks.append(" ".join(chunk))
        i += max_words - overlap
    return chunks

def get_page_for_text(pdf_path, snippet):
    try:
        doc = fitz.open(pdf_path)
        for num, page in enumerate(doc, 1):
            if snippet[:40].strip() in page.get_text("text"):
                return num
        return 1
    except:
        return 1

# -------------------- Main logic --------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    start = time.time()

    print("🔍 Έλεγχος αλλαγών...")
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        # backward compatibility
        for k, v in list(cache.items()):
            if isinstance(v, str):
                cache[k] = {"hash": v, "metadata": []}

    existing_docs = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    deleted_docs = [f for f in cache.keys() if f not in existing_docs]
    changed_docs = []

    for f in existing_docs:
        path = os.path.join(DOCS_PATH, f)
        h = get_file_hash(path)
        if f not in cache or cache[f]["hash"] != h or args.rebuild:
            changed_docs.append(f)
        cache[f] = {"hash": h, "metadata": cache.get(f, {}).get("metadata", [])}

    if not changed_docs and not deleted_docs and not args.rebuild:
        print("✅ Κανένα αρχείο δεν άλλαξε — παράλειψη indexing.")
        return

    for f in deleted_docs:
        print(f"🗑️ Διαγραφή: {f}")
        pdf_path = os.path.join(PDF_PATH, os.path.splitext(f)[0] + ".pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        cache.pop(f, None)

    metadata, chunks = [], []
    for i, fname in enumerate(changed_docs, 1):
        print(f"📘 ({i}/{len(changed_docs)}) Επεξεργασία: {fname}")
        path = os.path.join(DOCS_PATH, fname)
        pdf = convert_to_pdf(path, PDF_PATH)
        sections = read_docx_sections(path)
        file_meta = []
        for si, sec in enumerate(sections):
            for ci, chunk in enumerate(chunk_text(sec["text"], CHUNK_SIZE, CHUNK_OVERLAP)):
                page = get_page_for_text(pdf, chunk)
                entry = {
                    "filename": fname,
                    "section_title": sec["title"],
                    "section_idx": si,
                    "chunk_id": ci,
                    "page": page,
                    "text": chunk
                }
                metadata.append(entry)
                file_meta.append(entry)
                chunks.append(chunk)
        cache[fname]["metadata"] = file_meta
        print(f"✅ Ολοκληρώθηκε: {fname} ({len(file_meta)} chunks)")

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    if not chunks:
        print("⚙️ Δεν υπάρχουν νέα δεδομένα προς embedding.")
        return

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")
    print("🧠 Δημιουργία embeddings μόνο για νέα/τροποποιημένα αρχεία...")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, INDEX_FILE)
    print(f"✅ Ολοκληρώθηκε! ({time.time()-start:.1f}s)")

if __name__ == "__main__":
    main()
