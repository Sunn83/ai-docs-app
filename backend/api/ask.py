# backend/api/ask.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

# Φόρτωση embedding model (με cache)
model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ Δεν βρέθηκε FAISS index ή metadata.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS index και metadata φορτώθηκαν στη μνήμη.")

class Query(BaseModel):
    question: str

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        q_emb = model.encode([question])
        q_emb = np.array(q_emb).astype("float32")

        # 🟢 DEBUG
        print("Question:", question)
        print("Embedding shape:", q_emb.shape)
        print("Index ntotal:", index.ntotal)
        
        # top 3 αποτελέσματα
        D, I = index.search(q_emb, k=3)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                results.append({
                    "filename": metadata[idx]["filename"],
                    "text": metadata[idx]["text"],
                    "distance": float(score)
                })

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question}

                # Πάρε το πιο σχετικό chunk (πρώτο αποτέλεσμα)
        top_result = results[0]
        answer_text = top_result["text"].strip()

        # Αν υπάρχει επόμενο chunk στο ίδιο αρχείο, ένωσέ το (π.χ. συνέχεια της παραγράφου)
        idx = top_result.get("chunk_id", None)
        filename = top_result["filename"]

        if idx is not None:
            # Βρες το επόμενο chunk αν υπάρχει
            next_chunk = next(
                (m["text"] for m in metadata if m["filename"] == filename and m["chunk_id"] == idx + 1),
                None
            )
            if next_chunk:
                answer_text += "\n" + next_chunk.strip()

        return {
            "answer": answer_text,
            "source": filename,
            "query": question
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
