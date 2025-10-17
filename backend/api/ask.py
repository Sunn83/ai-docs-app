from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

# Φόρτωση μοντέλου embeddings και FAISS index στη μνήμη
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("FAISS ή metadata αρχείο δεν βρέθηκαν στο /data.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS και metadata φορτώθηκαν στη μνήμη.")


class Query(BaseModel):
    question: str


@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # Μετατροπή της ερώτησης σε embedding
        q_emb = model.encode([question])
        q_emb = np.array(q_emb).astype("float32")

        # Αναζήτηση στα FAISS embeddings
        D, I = index.search(q_emb, k=3)  # top 3 πιο σχετικά

        # Δημιουργία λίστας αποτελεσμάτων
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                results.append({
                    "filename": metadata[idx]["filename"],
                    "text": metadata[idx]["text"],
                    "distance": float(score)
                })

        return {"query": question, "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
