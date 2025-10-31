# backend/api/ask.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os, traceback
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"
DEBUG_FILE = "/data/last_query_debug.json"

# load model
model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ Δεν βρέθηκε FAISS index ή metadata.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS index και metadata φορτώθηκαν στη μνήμη. ntotal=", index.ntotal)


class Query(BaseModel):
    question: str

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # embedding
        q_emb = model.encode([question], convert_to_numpy=True)
        q_emb = np.array(q_emb).astype("float32")
        faiss.normalize_L2(q_emb)  # αν index είναι normalized

        # debug
        print("---- QUERY DEBUG ----")
        print("Question:", question)
        print("q_emb shape:", q_emb.shape)
        print("Index ntotal:", index.ntotal)

        k = min(8, int(index.ntotal) or 3)  # top k
        D, I = index.search(q_emb, k=k)

        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx < len(metadata):
                md = metadata[idx]
                results.append({
                    "idx": int(idx),
                    "distance": float(dist),
                    "filename": md.get("filename"),
                    "section_title": md.get("section_title"),
                    "section_idx": md.get("section_idx"),
                    "chunk_id": md.get("chunk_id"),
                    "text_preview": md.get("text")[:800]  # preview only
                })
        # sort by distance descending if using IP (cosine) or ascending for L2
        # (we stored as IP normalized; adjust if using L2)
        # Print debug
        print("Matches:", json.dumps(results, ensure_ascii=False, indent=2))

        # save debug file to inspect in container/host
        debug_dump = {
            "question": question,
            "matches": results,
            "ntotal": int(index.ntotal)
        }
        try:
            with open(DEBUG_FILE, "w", encoding="utf-8") as df:
                json.dump(debug_dump, df, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Could not write debug file:", e)

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question, "matches": []}

        # Compose answer: return the full chunk text of best match (not only preview)
        best = results[0]
        full_text = metadata[best["idx"]]["text"]

        # create readable answer: combine best chunk + next few chunks from same section (if any)
        merged = [full_text]
        # try to append neighboring chunks from same file/section
        for r in results[1:4]:
            if r["filename"] == best["filename"] and r["section_idx"] == best["section_idx"]:
                merged.append(metadata[r["idx"]]["text"])

        answer_text = "\n\n".join(merged).strip()

        return {
            "answer": answer_text,
            "source": best["filename"],
            "query": question,
            "matches": results
        }

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in /api/ask:", str(e))
        print(tb)
        raise HTTPException(status_code=500, detail=str(e))
