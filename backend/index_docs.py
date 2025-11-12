import os
import json
import hashlib
import argparse
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re
import subprocess
import fitz
import time


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
def get_file_hash(filepath):
    h = hashlib.sha1()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

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
        text = "".join(parts).replace("\u00A0", " ").replace("\r", "").strip()
        return text

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
        all_text = "\n".join([get_paragraph_text_with_breaks(p) for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]
    return sections

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

def get_page_for_text(pdf_path, text_snippet, page_cache=None, chunk_id=None):
    if page_cache is not None and chunk_id in page_cache:
        return page_cache[chunk_id]
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

def load_docs(rebuild=False):
    metadata, all_chunks = [], []

    os.makedirs(PDF_PATH, exist_ok=True)

    # Load cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    # Track existing files to remove deleted ones
    existing_files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]
    deleted_files = [f for f in cache.keys() if f not in existing_files]
    for f in deleted_files:
        print(f"🗑️ Αφαιρέθηκε: {f} → διαγράφονται chunks και PDF")
        # Remove PDF
        pdf_file = os.path.join(PDF_PATH, os.path.splitext(f)[0]+".pdf")
        if os.path.exists(pdf_file):
            os.remove(pdf_file)
        # Remove cache entry
        cache.pop(f, None)

    for i, fname in enumerate(existing_files, start=1):
        path = os.path.join(DOCS_PATH, fname)
        file_hash = get_file_hash(path)

        # Check cache
        skip_file = fname in cache and cache[fname]["hash"] == file_hash and not rebuild
        if skip_file:
            print(f"⏩ Παράλειψη (δεν άλλαξε): {fname}")
            # load chunks and metadata from previous cache
            for chunk_entry in cache[fname]["metadata"]:
                metadata.append(chunk_entry)
                all_chunks.append(chunk_entry["text"])
            continue

        print(f"📘 ({i}/{len(existing_files)}) Επεξεργασία: {fname}")
        pdf_path = convert_to_pdf(path, PDF_PATH)
        sections = read_docx_sections(path)
        file_cache = {"hash": file_hash, "pages": {}, "metadata": []}

        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks and sec_text.strip():
                chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                page = get_page_for_text(pdf_path, chunk, file_cache["pages"], chunk_id=str(cj))
                file_cache["pages"][str(cj)] = page
                entry = {
                    "filename": fname,
                    "pdf_path": pdf_path,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "page": page,
                    "text": chunk
                }
                metadata.append(entry)
                all_chunks.append(chunk)
                file_cache["metadata"].append(entry)

        cache[fname] = file_cache
        print(f"✅ Ολοκληρώθηκε: {fname} ({len(sections)} ενότητες)")

    # Save cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    return all_chunks, metadata

def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index

# ---------------------------------------------------
# 🔹 Υπολογισμός hash αρχείου για ανίχνευση αλλαγών
# ---------------------------------------------------
def compute_file_hash(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha.update(chunk)
    return sha.hexdigest()

# ---------------------------------------------------
# 🔹 Φόρτωση υπάρχοντος cache state (αν υπάρχει)
# ---------------------------------------------------
def load_existing_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ---------------------------------------------------
# 🔹 Αποθήκευση cache state
# ---------------------------------------------------
def save_cache_state(cache_data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------
# 🔹 ΝΕΑ main() με πλήρες caching & smart rebuild
# ---------------------------------------------------
def main():
    start_time = time.time()

    print("🔍 Έλεγχος αλλαγών στα αρχεία...")
    old_cache = load_existing_cache()
    new_cache = {}
    changed_files = []
    deleted_files = []

    doc_files = [f for f in os.listdir(DOCS_PATH) if f.lower().endswith(".docx")]

    # Έλεγχος νέων ή τροποποιημένων αρχείων
    for f in doc_files:
        fpath = os.path.join(DOCS_PATH, f)
        new_hash = compute_file_hash(fpath)
        new_cache[f] = new_hash
        if f not in old_cache or old_cache[f] != new_hash:
            changed_files.append(f)

    # Έλεγχος για διαγραμμένα αρχεία
    deleted_files = [f for f in old_cache if f not in new_cache]

    # ✅ Αν δεν υπάρχει ούτε αλλαγή ούτε διαγραφή → SKIP ΠΑΝΤΑ
    if not changed_files and not deleted_files and os.path.exists(INDEX_FILE):
        print("✅ Κανένα αρχείο δεν άλλαξε — παράλειψη δημιουργίας FAISS index.")
        print("   (παράλειψη και του load_docs, δεν τρέχουν embeddings)")
        return  # 🔥 εδώ σταματάμε τα πάντα 🔥

    # Αν έφτασες εδώ, σημαίνει ότι υπάρχουν αλλαγές ή διαγραφές
    if changed_files:
        print(f"📝 Αρχεία προς επεξεργασία ({len(changed_files)}): {changed_files}")
    if deleted_files:
        print(f"🗑️ Διαγραφή metadata για αρχεία: {deleted_files}")

    # ⚙️ μόνο τώρα φορτώνουμε docx (αν υπάρχει αλλαγή)
    chunks, metadata = load_docs()

    metadata = [m for m in metadata if m["filename"] not in deleted_files]

    print(f"➡️ Συνολικά {len(chunks)} chunks προς επεξεργασία.")
    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode([f"passage: {c}" for c in chunks], convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")

    print("🔧 Κανονικοποίηση embeddings (L2) + δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    # Αποθήκευση metadata & cache
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    save_cache_state(new_cache)

    # Διαγραφή PDF για όσα αρχεία αφαιρέθηκαν
    for df in deleted_files:
        pdf_path = os.path.join(PDF_PATH, os.path.splitext(df)[0] + ".pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"🗑️ Διαγράφηκε PDF: {os.path.basename(pdf_path)}")

    elapsed = time.time() - start_time
    print(f"✅ Indexing ολοκληρώθηκε ({elapsed:.1f} sec)!")

if __name__ == "__main__":
    main()
