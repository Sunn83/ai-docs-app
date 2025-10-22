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
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return text

def chunk_text(text, chunk_size=300, overlap=50):
    # Σπάσε σε προτάσεις (με βάση . ? !)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        words = sent.split()
        sent_len = len(words)

        # Αν προσθέσουμε την πρόταση και ξεπερνάμε το όριο chunk_size -> κόψε εδώ
        if current_len + sent_len > chunk_size:
            chunks.append(" ".join(current_chunk))
            # Κρατάμε overlap (τελευταίες προτάσεις από το προηγούμενο chunk)
            overlap_words = " ".join(" ".join(current_chunk).split()[-overlap:])
            current_chunk = [overlap_words, sent]
            current_len = sent_len + overlap
        else:
            current_chunk.append(sent)
            current_len += sent_len

    # Πρόσθεσε το τελευταίο chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

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
