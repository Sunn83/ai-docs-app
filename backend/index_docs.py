# backend/index_docs.py
import os
import json
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

# 📏 Ρυθμίσεις chunking (πιο μεγάλα chunks για καλύτερα context)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# ✅ Μετατροπή πίνακα σε Markdown
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
        # ⚙️ αντί για <br> βάλε απλό διάστημα (για να μην εμφανίζονται στο frontend)
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

# ✅ Ανάγνωση docx με δομή και πίνακες
def read_docx_sections(filepath):
    doc = Document(filepath)
    sections = []
    current_title = None
    current_body = []

    def flush_section():
        nonlocal current_title, current_body
        if not current_title and not current_body:
            return
        text = "\n".join([t.strip() for t in current_body if t.strip()])
        if text.strip():
            sections.append({
                "title": current_title.strip() if current_title else None,
                "text": text.strip()
            })
        current_title = None
        current_body = []

    for block in doc.element.body:
        if block.tag.endswith("p"):
            txt = block.text.strip() if hasattr(block, "text") else ""
            if not txt:
                continue
            style = ""
            try:
                style = block.style.name.lower()
            except Exception:
                pass
            if style.startswith("heading") or "επικεφαλίδα" in style or re.match(r"^\s*(άρθρο|ενότητα|θέμα|\d+(\.\d+)+)", txt.lower()):
                flush_section()
                current_title = txt
                continue
            current_body.append(txt)

        elif block.tag.endswith("tbl"):
            try:
                table = next(t for t in doc.tables if t._element == block)
            except StopIteration:
                continue
            table_md = table_to_markdown(table)
            if table_md.strip():
                current_body.append(table_md)

    flush_section()
    if not sections:
        all_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]
    return sections

def chunk_section_text(section_text, max_words=500, overlap_words=100):
    """
    Σπάει το κείμενο σε chunks ΜΟΝΟ εκτός markdown πινάκων.
    Αν εντοπίσει φράση για πίνακα ("κάτωθι πίνακα", "βλέπε πίνακα" κ.λπ.)
    πριν από τον πίνακα, τον ενσωματώνει στο ίδιο chunk.
    """
    if not section_text:
        return []

    # Διάσπαση με βάση πίνακες
    parts = re.split(r'(?=📊 Πίνακας:)', section_text)
    chunks = []
    prev_part = ""

    join_triggers = ["πίνακα", "πίνακας", "κάτωθι πίνακα", "παρακάτω πίνακα", "ακόλουθο πίνακα", "βλέπε πίνακα", "πίνακα:"]

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Αν το κομμάτι είναι πίνακας
        if part.startswith("📊 Πίνακας:"):
            # ➕ Αν το προηγούμενο αναφέρει πίνακα, συγχώνευσέ τα
            if prev_part and any(trig in prev_part.lower() for trig in join_triggers):
                prev_part = prev_part.rstrip() + "\n\n" + part.strip()
                chunks[-1] = prev_part
                prev_part = ""
            else:
                chunks.append(part)
            continue

        # Κανονικό κείμενο — split σε προτάσεις
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
            prev_part = joined  # αποθήκευσε για πιθανό πίνακα μετά

    # Καθάρισε μικρά/κενά chunks
    chunks = [c for c in chunks if len(c.split()) > 5]
    return chunks

def load_docs():
    metadata, all_chunks = [], []
    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks:
                if sec_text.strip():
                    chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                metadata.append({
                    "filename": fname,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "text": chunk
                })
                all_chunks.append(chunk)
    return all_chunks, metadata

def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index

def main():
    print("📄 Φόρτωση DOCX αρχείων...")
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
