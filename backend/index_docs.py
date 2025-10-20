# backend/index_docs.py
import os
import json
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import faiss

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

# Παράμετροι chunking
CHUNK_SIZE = 300  # λέξεις ανά chunk
CHUNK_OVERLAP = 50  # επικάλυψη λέξεων

def read_docx(file_path):
    doc = Document(file_path)
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
    return text

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
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
    print("📄 Βρέθηκαν αρχεία για επεξεργασία...")
    chunks, metadata = load_docs()
    print(f"Βρέθηκαν {len(chunks)} chunks για επεξεργασία.")

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("thenlper/gte-large")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode(chunks, convert_to_numpy=True)

    print("💾 Δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε με επιτυχία!")

if __name__ == "__main__":
    main()
