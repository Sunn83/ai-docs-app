from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os, re
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

# 🔹 Φόρτωση μοντέλου και index
model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ Δεν βρέθηκε FAISS index ή metadata.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS index και metadata φορτώθηκαν στη μνήμη.")

class Query(BaseModel):
    question: str

# ✅ Καθαρισμός κειμένου, διατηρεί newlines
def clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # 🔹 Encode query
        q_emb = model.encode([f"query: {question}"], convert_to_numpy=True)
        q_emb = q_emb.astype('float32')
        faiss.normalize_L2(q_emb)

        # 🔹 Αναζήτηση FAISS
        k = 7
        D, I = index.search(q_emb, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                md = metadata[idx]
                results.append({
                    "idx": int(idx),
                    "score": float(score),
                    "filename": md["filename"],
                    "section_title": md.get("section_title"),
                    "section_idx": md.get("section_idx"),
                    "chunk_id": md.get("chunk_id"),
                    "text": md.get("text")
                })

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question}

        # 🔹 Συγχώνευση chunks ανά ενότητα
        merged_by_section = {}
        for r in results:
            key = (r["filename"], r.get("section_idx"))
            merged_by_section.setdefault(key, {"chunks": [], "scores": []})
            merged_by_section[key]["chunks"].append((r["chunk_id"], r["text"]))
            merged_by_section[key]["scores"].append(r["score"])

        merged_list = []
        for (fname, sidx), val in merged_by_section.items():
            sorted_chunks = [t for _, t in sorted(val["chunks"], key=lambda x: x[0])]
            joined = "\n\n".join(sorted_chunks)
            avg_score = float(sum(val["scores"]) / len(val["scores"]))
            merged_list.append({
                "filename": fname,
                "section_idx": sidx,
                "text": joined,
                "score": avg_score,
                "chunk_id": val["chunks"][0][0] if val["chunks"] else 0
            })

        merged_list = sorted(merged_list, key=lambda x: x["score"], reverse=True)
        best = merged_list[0]

        # ✨ Καθάρισμα κειμένου
        answer_text = clean_text(best["text"])

        # ✨ Προσθήκη πηγής στο τέλος
        answer_text += f"\n\n📄 Πηγή: {best['filename']}\n📑 Section: {best['section_idx']} | Chunk: {best['chunk_id']}"

        MAX_CHARS = 4000
        if len(answer_text) > MAX_CHARS:
            answer_text = answer_text[:MAX_CHARS].rsplit(' ', 1)[0] + " ..."

        return {
            "answer": answer_text,
            "query": question
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
