from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import faiss
import pickle
from sentence_transformers import SentenceTransformer
import numpy as np

app = FastAPI()

# CORS για frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ή ["https://το-domain-σου"] όταν έχεις frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

# Φόρτωσε FAISS και metadata
index = faiss.read_index("/data/faiss.index")
with open("/data/docs_meta.pkl", "rb") as f:
    docs_meta = pickle.load(f)

# Φόρτωσε μοντέλο embeddings
model = SentenceTransformer("all-MiniLM-L6-v2")

# API για ερωτήσεις
@app.get("/api/ask")
def ask(q: str = Query(..., min_length=1)):
    # Δημιουργία embedding για την ερώτηση
    q_vec = model.encode([q], convert_to_numpy=True)

    # Αναζήτηση στον FAISS
    k = 3  # πόσα κοντινά chunks θέλουμε
    D, I = index.search(q_vec, k)

    results = []
    for idx in I[0]:
        if idx < len(docs_meta):
            chunk = docs_meta[idx]
            results.append({
                "text": chunk["text"],
                "source": chunk["filename"]
            })

    return {"answer": results}
