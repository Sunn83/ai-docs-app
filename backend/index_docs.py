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

import re

def chunk_text(text):
    """
    Σπάει το έγγραφο σε ενότητες με βάση τους τίτλους τύπου:
    '1.', '2.1', '2.4 Διοικητική κύρωση ...' κ.λπ.
    Κάθε ενότητα περιλαμβάνει τον τίτλο + το περιεχόμενο μέχρι τον επόμενο τίτλο.
    """
    # regex: τίτλοι τύπου "1.", "2.3", "3.1.4", "2.4 Διοικητική κύρωση ..."
    pattern = r"(?=(?:\n|^)(\d+(?:\.\d+)*\s+[^:\n]+:))"

    sections = re.split(pattern, text)
    chunks = []

    # Αν δεν υπάρχουν matches, επέστρεψε όλο το κείμενο σαν ένα chunk
    if len(sections) <= 1:
        return [text]

    # Κάθε δύο στοιχεία του split = [τίτλος, περιεχόμενο]
    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""
        full_chunk = f"{title}\n{content}"
        chunks.append(full_chunk.strip())

    return chunks

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
