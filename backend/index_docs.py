# backend/index_docs.py
import os
import json
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import faiss
import re

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

# Ρυθμίσεις chunking
CHUNK_SIZE = 350  # λέξεις ανά chunk
CHUNK_OVERLAP = 50  # επικάλυψη

def read_docx(file_path):
    doc = Document(file_path)
    parts = []
    current_heading = None

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue

        style_name = ""
        try:
            style_name = getattr(p.style, "name", "") or ""
        except Exception:
            pass

        # Ελέγχουμε αν είναι επικεφαλίδα (αγγλικά ή ελληνικά)
        if "heading" in style_name.lower() or "επικεφαλίδα" in style_name.lower():
            current_heading = text
            continue

        # Αν έχουμε heading, προσθέτουμε το περιεχόμενο με prefix
        if current_heading:
            parts.append(f"{current_heading}: {text}")
        else:
            parts.append(text)

    return "\n".join(parts)

def split_by_headings(text):
    """
    Σπάει το docx σε ενότητες με βάση επικεφαλίδες τύπου '2.4 ...' ή 'Άρθρο ...'
    """
    # Κανονική έκφραση που εντοπίζει επικεφαλίδες (π.χ. 2.4, 3.1, Άρθρο 5, Θέμα)
    pattern = re.compile(r'(?=\n?\s*(?:\d+\.\d+|Άρθρο\s+\d+|Θέμα|Ενότητα)\b)', re.IGNORECASE)
    parts = pattern.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 50]  # αγνόησε πολύ μικρά

def chunk_text(text, chunk_size=350, overlap=50):
    """
    Δημιουργεί chunks ~350 λέξεων μέσα σε κάθε ενότητα (όχι σε όλο το κείμενο).
    """
    sections = split_by_headings(text)
    all_chunks = []

    for sec in sections:
        sentences = re.split(r'(?<=[.!;?])\s+', sec)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_len = 0

        for sent in sentences:
            words = sent.split()
            sent_len = len(words)

            if current_len + sent_len > chunk_size:
                chunks.append(" ".join(current_chunk))
                overlap_text = " ".join(" ".join(current_chunk).split()[-overlap:])
                current_chunk = [overlap_text, sent]
                current_len = len(overlap_text.split()) + sent_len
            else:
                current_chunk.append(sent)
                current_len += sent_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        all_chunks.extend(chunks)

    return all_chunks

def load_docs():
    metadata = []
    all_chunks = []
    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        text = read_docx(path)
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            metadata.append({
                "filename": fname,
                "chunk_id": idx,
                "text": chunk
            })
            all_chunks.append(chunk)
    return all_chunks, metadata

def create_faiss_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
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

    print("💾 Δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")

if __name__ == "__main__":
    main()
