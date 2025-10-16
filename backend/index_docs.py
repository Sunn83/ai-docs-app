import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from docx import Document

DOCS_PATH = os.getenv("DOCS_PATH", "/data/docs")
DATA_PATH = os.getenv("DATA_PATH", "/data")
DOCS_PATH = os.path.join(DATA_PATH, "docs")
INDEX_FILE = os.path.join(DATA_PATH, "faiss.index")
META_FILE = os.path.join(DATA_PATH, "docs_meta.json")

# Chunking function
def chunk_text(text, max_words=200):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i+max_words]))
    return chunks

def load_docs():
    docs = []
    for fname in os.listdir(DOCS_PATH):
        if fname.endswith(".docx"):
            path = os.path.join(DOCS_PATH, fname)
            doc = Document(path)
            full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            chunks = chunk_text(full_text)
            for c in chunks:
                docs.append({"filename": fname, "text": c})
    return docs

def build_index(docs):
    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print("🧠 Δημιουργία embeddings για chunks...")
    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
    
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity)
    index.add(embeddings)
    faiss.write_index(index, INDEX_FILE)
    
    # Save metadata
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"💾 FAISS index αποθηκεύτηκε στο: {INDEX_FILE}")
    print(f"💾 Metadata αποθηκεύτηκαν στο: {META_FILE}")

if __name__ == "__main__":
    docs = load_docs()
    print(f"📄 Βρέθηκαν {len(docs)} chunks για επεξεργασία.")
    build_index(docs)
    print("🎉 Indexing ολοκληρώθηκε με επιτυχία!")
