# api/ask.py — ουσιαστικό μέρος
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

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

        # encode + normalize
        q_emb = model.encode([question], convert_to_numpy=True)
        q_emb = q_emb.astype('float32')
        faiss.normalize_L2(q_emb)

        # πάρε top-k
        k = 7
        D, I = index.search(q_emb, k)

        # build results — πρόσεξε: metadata είναι list με ίδια σειρά που φτιάχτηκε ο index
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                results.append({
                    "idx": int(idx),
                    "score": float(score),
                    "filename": metadata[idx]["filename"],
                    "chunk_id": metadata[idx].get("chunk_id"),
                    "text": metadata[idx]["text"]
                })

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question}

        # Συγχώνευση γειτονικών chunks από το ίδιο αρχείο (π.χ. chunk_id συνεχόμενα)
        merged = []
        for r in results:
            if not merged:
                merged.append(r)
                continue
            prev = merged[-1]
            # αν ίδιο αρχείο και συνεχόμενο chunk_id -> συγχώνευσε
            if r["filename"] == prev["filename"] and prev.get("chunk_id") is not None and r.get("chunk_id") is not None and r["chunk_id"] == prev["chunk_id"] + 1:
                prev["text"] = prev["text"].rstrip() + " " + r["text"].lstrip()
                prev["score"] = max(prev["score"], r["score"])
            else:
                merged.append(r)

        top = merged[0]
        # Επέκτεινε απάντηση στα top 1-2 merged results ώστε να δώσεις πλήρες context
        answer_text = top["text"]
        if len(merged) > 1 and merged[1]["filename"] == top["filename"]:
            answer_text = answer_text + "\n\n" + merged[1]["text"]

        # Καθάρισμα & trim (π.χ. αν είναι πολύ μεγάλο)
        answer_text = " ".join(answer_text.split())
        MAX_CHARS = 3000
        if len(answer_text) > MAX_CHARS:
            answer_text = answer_text[:MAX_CHARS] + " ..."

        return {
            "answer": answer_text,
            "source": top["filename"],
            "query": question,
            "matches": merged[:5]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
