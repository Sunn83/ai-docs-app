import os
import json
import faiss
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from api.ask import router as ask_router

app = FastAPI()
app.include_router(ask_router)

DATA_PATH = os.getenv("DATA_PATH", "./data")
INDEX_FILE = os.path.join(DATA_PATH, "faiss.index")
META_FILE = os.path.join(DATA_PATH, "docs_meta.json")

if os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
    index = faiss.read_index(INDEX_FILE)
    with open(META_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print("FAISS index και metadata φορτώθηκαν επιτυχώς!")
else:
    index = None
    metadata = {}
    print("FAISS index ή metadata δεν βρέθηκαν. Τρέξε πρώτα το reindex.sh")
with open(META_FILE, "r", encoding="utf-8") as f:
    meta = json.load(f)

print("🔍 Φόρτωση μοντέλου embeddings για ερωτήσεις...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class Question(BaseModel):
    question: str

@app.post("/api/ask")
def ask_question(q: Question):
    query_embedding = model.encode([q.question], convert_to_numpy=True, normalize_embeddings=True)
    D, I = index.search(query_embedding, k=3)  # Top 3 chunks
    results = []
    for score, idx in zip(D[0], I[0]):
        chunk = meta[idx]
        results.append({
            "filename": chunk["filename"],
            "text": chunk["text"],
            "score": float(score)
        })
    # Συνδυασμός απάντησης
    answer = " ".join([r["text"] for r in results[:1]])  # Πρώτο καλύτερο chunk
    return {"answer": answer, "top_chunks": results}
