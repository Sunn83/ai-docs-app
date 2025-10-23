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

# Ρυθμίσεις chunking
CHUNK_SIZE = 350  # λέξεις ανά chunk
CHUNK_OVERLAP = 50  # επικάλυψη

# --- section-aware reading & chunking (βάλε στο backend/index_docs.py) ---
from docx import Document
import re

def read_docx_sections(file_path):
    """
    Επιστρέφει λίστα sections: κάθε section = {"title": title_or_none, "text": full_text}
    Προσπαθεί να χρησιμοποιήσει paragraph styles (Heading...), αλλιώς αν δεν υπάρχουν,
    ανιχνεύει γραμμές που τερματίζουν σε ':' ή είναι σύντομες ως τίτλους.
    """
    doc = Document(file_path)
    sections = []
    current_title = None
    current_body = []

    def flush_section():
        if current_title is None and not current_body:
            return
        text = "\n".join([t for t in current_body if t.strip()])
        sections.append({
            "title": current_title.strip() if current_title else None,
            "text": text.strip()
        })

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            # blank line -> skip but keep in body
            continue

        # case 1: style indicates heading (Heading 1/2/3) — συνήθως "Heading 1" κλπ
        style_name = getattr(p.style, "name", "") or ""
        if style_name.lower().startswith("heading") or style_name.lower().startswith("επικεφαλίδα"):
            # new section
            if current_title is not None or current_body:
                flush_section()
            current_title = txt
            current_body = []
            continue

        # case 2: fallback heading detection (short line or endswith ':')
        if (len(txt.split()) <= 8 and txt.endswith(":")) or (len(txt) <= 60 and len(txt.split()) <= 5 and txt.endswith(":")):
            # treat as title
            if current_title is not None or current_body:
                flush_section()
            current_title = txt
            current_body = []
            continue

        # else: normal paragraph -> append to body
        current_body.append(txt)

    # flush last
    if current_title is not None or current_body:
        flush_section()

    # If file has NO headings at all, create 1 section with whole text
    if not sections:
        # fallback: join paragraphs into single section
        doc_text = "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": doc_text}]

    return sections

def chunk_section_text(section_text, max_words=400, overlap_words=60):
    """
    Με βάση λέξεις - σπάει τη section σε chunks, κρατώντας sentences ακέραιες.
    Επιστρέφει λίστα chunk strings.
    """
    if not section_text:
        return []

    # split σε προτάσεις (βασικά με ., ?, ! αλλά διατηρούμε ελληνικά)
    sentences = re.split(r'(?<=[\.\!\?])\s+', section_text.strip())
    chunks = []
    cur = []
    cur_count = 0

    for s in sentences:
        words = s.split()
        wcount = len(words)
        if cur_count + wcount > max_words and cur:
            chunks.append(" ".join(cur).strip())
            # overlap: keep last overlap_words words from cur
            tail = " ".join(" ".join(cur).split()[-overlap_words:])
            cur = [tail, s]
            cur_count = len(tail.split()) + wcount
        else:
            cur.append(s)
            cur_count += wcount

    if cur:
        chunks.append(" ".join(cur).strip())

    # dedupe empty and very short
    chunks = [c for c in chunks if len(c.split()) > 5]
    return chunks

def load_docs():
    """
    Επιστρέφει: chunks_list, metadata_list (ordered lists)
    metadata entries: {"filename": fname, "section_title": title, "section_idx": i_section, "chunk_id": j_chunk}
    """
    metadata = []
    all_chunks = []
    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            # split section to chunks
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks:
                # if section was too small, keep whole section text
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


def split_by_headings(text):
    """
    Σπάει το docx σε ενότητες με βάση επικεφαλίδες τύπου '2.4 ...' ή 'Άρθρο ...'
    """
    # Κανονική έκφραση που εντοπίζει επικεφαλίδες (π.χ. 2.4, 3.1, Άρθρο 5, Θέμα)
    pattern = re.compile(r'(?=\n?\s*(?:\d+\.\d+|Άρθρο\s+\d+|Θέμα|Ενότητα)\b)', re.IGNORECASE)
    parts = pattern.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 50]  # αγνόησε πολύ μικρά

def create_faiss_index(embeddings):
    # normalize για cosine similarity
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # inner product (cosine if normalized)
    index.add(embeddings)
    return index

def main():
    print("📄 Φόρτωση DOCX αρχείων...")
    chunks, metadata = load_docs()
    print(f"➡️  Βρέθηκαν {len(chunks)} chunks προς επεξεργασία.")

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=True)

    # convert to float32 if όχι ήδη
    embeddings = embeddings.astype('float32')

    print("🔧 Κανονικοποίηση embeddings (L2) + δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    main()
