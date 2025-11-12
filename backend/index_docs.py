import os, json, hashlib, argparse, time, re, subprocess, fitz
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

# -------------------- Config --------------------
DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
PDF_PATH = os.path.join(DATA_DIR, "pdfs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")
CACHE_FILE = os.path.join(DATA_DIR, "index_cache.json")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# -------------------- Helpers --------------------
def compute_file_hash(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha.update(chunk)
    return sha.hexdigest()

def table_to_markdown(table):
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(" | ".join(cells))
    if not rows:
        return ""
    num_cols = len(rows[0].split("|"))
    sep = " | ".join(["---"] * num_cols)
    return "\n📊 Πίνακας:\n" + rows[0] + "\n" + sep + "\n" + "\n".join(rows[1:])

def read_docx_sections(filepath):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(filepath)
    sections = []
    current_title, current_body = None, []

    def flush_section():
        nonlocal current_title, current_body
        if current_body:
            text = "\n\n".join([t.strip() for t in current_body if t.strip()])
            if text:
                sections.append({"title": current_title, "text": text})
        current_title, current_body = None, []

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            txt = p.text.strip()
            if not txt:
                continue
            style = p.style.name.lower() if p.style else ""
            if style.startswith("heading") or re.match(r"^\s*(άρθρο|ενότητα|\d+(\.\d+)+)", txt.lower()):
                flush_section()
                current_title = txt
            else:
                current_body.append(txt)
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            md = table_to_markdown(t)
            if md.strip():
                current_body.append(md)
    flush_section()
    if not sections:
        all_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        sections = [{"title": None, "text": all_text}]
    return sections

def chunk_text(text, max_words=500, overlap=100):
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks, cur, count = [], [], 0
    for s in sentences:
        words = len(s.split())
        if count + words > max_words and cur:
            joined = " ".join(cur).strip()
            chunks.append(joined)
            overlap_part = " ".join(joined.split()[-overlap:])
            cur, count = [overlap_part, s], len(overlap_part.split()) + words
        else:
            cur.append(s)
            count += words
    if cur:
        chunks.append(" ".join(cur).strip())
    return [c for c in chunks if len(c.split()) > 5]

def convert_to_pdf(docx_path, pdf_dir):
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_file = os.path.join(pdf_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
    if not os.path.exists(pdf_file):
        print(f"⚙️ Μετατροπή σε PDF: {os.path.basename(docx_path)}")
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf",
            "--outdir", pdf_dir, docx_path
        ], check=True)
    return pdf_file

def get_page_for_text(pdf_path, snippet):
    try:
        doc = fitz.open(pdf_path)
        snippet = snippet[:300]
        for page_num, page in enumerate(doc, start=1):
            if snippet[:50].strip() in page.get_text("text"):
                return page_num
        return 1
    except Exception:
        return 1

# -------------------- Core --------------------
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def load_docs(cache, changed_files, deleted_files):
    metadata, all_chunks = [], []

    # Remove deleted files
    for f in deleted_files:
        if f in cache:
            print(f"🗑️ Αφαίρεση cache για {f}")
            cache.pop(f, None)
        pdf = os.path.join(PDF_PATH, os.path.splitext(f)[0] + ".pdf")
        if os.path.exists(pdf):
            os.remove(pdf)
            print(f"🗑️ Διαγράφηκε PDF: {pdf}")

    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        fpath = os.path.join(DOCS_PATH, fname)
        file_hash = compute_file_hash(fpath)

        # skip unchanged
        if fname in cache and cache[fname]["hash"] == file_hash and fname not in changed_files:
            for m in cache[fname]["metadata"]:
                metadata.append(m)
                all_chunks.append(m["text"])
            print(f"⏩ Παράλειψη (δεν άλλαξε): {fname}")
            continue

        print(f"📘 Επεξεργασία: {fname}")
        pdf_path = convert_to_pdf(fpath, PDF_PATH)
        sections = read_docx_sections(fpath)
        cache[fname] = {"hash": file_hash, "metadata": []}

        for si, sec in enumerate(sections):
            chunks = chunk_text(sec["text"], CHUNK_SIZE, CHUNK_OVERLAP)
            for cj, chunk in enumerate(chunks):
                page = get_page_for_text(pdf_path, chunk)
                entry = {
                    "filename": fname,
                    "pdf_path": pdf_path,
                    "section_title": sec.get("title"),
                    "section_idx": si,
                    "chunk_id": cj,
                    "page": page,
                    "text": chunk
                }
                metadata.append(entry)
                all_chunks.append(chunk)
                cache[fname]["metadata"].append(entry)

    save_cache(cache)
    return all_chunks, metadata, cache

def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index

def main():
    start = time.time()
    print("🔍 Έλεγχος αλλαγών...")

    cache = load_cache()
    files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    changed, deleted = [], []

    # Check changes
    for f in files:
        path = os.path.join(DOCS_PATH, f)
        new_hash = compute_file_hash(path)
        if f not in cache or cache[f]["hash"] != new_hash:
            changed.append(f)
    deleted = [f for f in cache.keys() if f not in files]

    if not changed and not deleted and os.path.exists(INDEX_FILE):
        print("✅ Κανένα αρχείο δεν άλλαξε — δεν δημιουργείται νέο FAISS index.")
        return

    print(f"📝 Αλλαγμένα: {changed or 'κανένα'}")
    print(f"🗑️ Διαγραμμένα: {deleted or 'κανένα'}")

    chunks, metadata, cache = load_docs(cache, changed, deleted)

    print(f"➡️ Βρέθηκαν {len(chunks)} chunks.")
    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")

    print("🔧 Δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    save_cache(cache)

    print(f"✅ Ολοκληρώθηκε ({time.time()-start:.1f}s)")

if __name__ == "__main__":
    main()
