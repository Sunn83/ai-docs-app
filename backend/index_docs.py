# backend/index_docs.py
import os
import json
import argparse
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re
import time

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "docspdf")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150
WORDS_PER_PAGE = 450  # για estimation page mapping

# ============= DOCX Parsing =============
def read_docx_sections(filepath):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(filepath)
    sections = []
    current_title = None
    current_body = []

    def flush_section():
        nonlocal current_title, current_body
        if current_body:
            text = "\n".join(current_body).strip()
            if text:
                sections.append({
                    "title": current_title,
                    "text": text
                })
        current_title, current_body = None, []

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            txt = p.text.strip()
            if not txt:
                continue
            style = ""
            try:
                style = p.style.name.lower()
            except Exception:
                pass
            if style.startswith("heading") or re.match(r"^\s*(άρθρο|ενότητα|θέμα|\d+(\.\d+)+)", txt.lower()):
                flush_section()
                current_title = txt
            else:
                current_body.append(txt)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            rows = []
            for r in table.rows:
                cells = [c.text.strip().replace("\n", " ") for c in r.cells]
                rows.append(" | ".join(cells))
            if rows:
                current_body.append("📊 Πίνακας:\n" + "\n".join(rows))
    flush_section()
    return sections if sections else [{"title": None, "text": "\n".join([p.text for p in doc.paragraphs if p.text.strip()])}]

# ============= Chunking =============
def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i + size])
        if chunk.strip():
            chunks.append(chunk)
        if i + size >= len(words):
            break
    return chunks

# ============= Incremental Indexing =============
def incremental_indexing(model):
    existing_meta = []
    index = None

    if os.path.exists(META_FILE) and os.path.exists(INDEX_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            existing_meta = json.load(f)
        index = faiss.read_index(INDEX_FILE)
        print(f"📚 Υπάρχουν ήδη {len(existing_meta)} καταχωρήσεις FAISS.")
    else:
        print("🆕 Δημιουργία νέου FAISS index...")
        index = None
        existing_meta = []

    known_files = {m["filename"] for m in existing_meta}
    current_files = {f for f in os.listdir(DOCS_PATH) if f.endswith(".docx")}
    new_files = current_files - known_files
    removed_files = known_files - current_files

    if not new_files and not removed_files:
        print("✅ Δεν υπάρχουν αλλαγές στα αρχεία DOCX. Το index είναι ενημερωμένο.")
        return

    if removed_files:
        print(f"🗑️ Διαγραφή metadata για: {', '.join(removed_files)}")
        existing_meta = [m for m in existing_meta if m["filename"] not in removed_files]
        index = None  # Rebuild all index if deletions occurred

    all_chunks, new_meta = [], []
    start_time = time.time()

    for i, fname in enumerate(sorted(new_files)):
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        pdf_name = Path(fname).stem + ".pdf"
        pdf_path = Path(PDF_PATH) / pdf_name
        pdf_url = f"/pdfs/{pdf_name}" if pdf_path.exists() else None

        print(f"📄 [{i+1}/{len(new_files)}] Επεξεργασία: {fname}")

        for si, sec in enumerate(sections):
            chunks = chunk_text(sec.get("text", ""))
            for cj, chunk in enumerate(chunks):
                words = len(chunk.split())
                new_meta.append({
                    "filename": fname,
                    "section_title": sec.get("title"),
                    "section_idx": si,
                    "chunk_id": cj,
                    "text": chunk,
                    "page_est": max(1, words // WORDS_PER_PAGE),
                    "pdf_link": pdf_url
                })
                all_chunks.append(chunk)

    if not all_chunks:
        print("⚠️ Δεν βρέθηκαν νέα chunks για indexing.")
        return

    print(f"🧠 Δημιουργία embeddings για {len(all_chunks)} chunks...")
    embeddings = model.encode([f"passage: {c}" for c in all_chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype('float32')
    faiss.normalize_L2(embeddings)

    if index is None:
        print("🔧 Δημιουργία νέου FAISS index...")
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        merged_meta = existing_meta + new_meta
    else:
        print("➕ Προσθήκη νέων vectors στο υπάρχον index...")
        index.add(embeddings)
        merged_meta = existing_meta + new_meta

    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(merged_meta, f, ensure_ascii=False, indent=2)

    elapsed = round(time.time() - start_time, 2)
    print(f"✅ Incremental indexing ολοκληρώθηκε ({elapsed}s).")
    print(f"📈 Νέα αρχεία: {len(new_files)} | Διαγραφές: {len(removed_files)} | Συνολικά: {len(merged_meta)} chunks.")

# ============= Main =============
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Αναγκαστικό rebuild από την αρχή")
    args = parser.parse_args()

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    if args.reset:
        print("♻️ Επαναδημιουργία πλήρους index από το μηδέν...")
        if os.path.exists(INDEX_FILE): os.remove(INDEX_FILE)
        if os.path.exists(META_FILE): os.remove(META_FILE)

    incremental_indexing(model)

if __name__ == "__main__":
    main()
