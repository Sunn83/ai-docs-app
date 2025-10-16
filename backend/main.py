import os
import json
import faiss
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()

# 🔧 Διαδρομές αρχείων
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

print("🔧 Φόρτωση FAISS index και metadata...")

if not os.path.exists(INDEX_FILE):
    raise FileNotFoundError(f"Το αρχείο index δεν βρέθηκε: {INDEX_FILE}")
if not os.path.exists(META_FILE):
    raise FileNotFoundError(f"Το αρχείο metadata δεν βρέθηκε: {META_FILE}")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class AskRequest(BaseModel):
    question: str

@app.post("/api/ask")
def ask(req: AskRequest):
    query = req.question.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Το ερώτημα δεν μπορεί να είναι κενό.")

    print(f"❓ Ερώτηση: {query}")

    query_embedding = model.encode([query])
    D, I = index.search(np.array(query_embedding, dtype=np.float32), k=1)

    best_idx = I[0][0]
    if best_idx >= len(metadata):
        raise HTTPException(status_code=500, detail="Μη έγκυρο αποτέλεσμα FAISS αναζήτησης.")

    best_doc = metadata[best_idx]
    response = {
        "answer": f"Το πιο σχετικό έγγραφο είναι το: {best_doc['filename']}",
        "document": best_doc,
        "distance": float(D[0][0]),
    }

    return response
