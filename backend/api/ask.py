# backend/api/ask.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os, re
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()
TOP_K = 3  # πόσες απαντήσεις θέλουμε να επιστρέφουμε
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

# ✅ Νέα clean_text που διατηρεί τις αλλαγές γραμμής
def clean_text(t: str) -> str:
    if not t:
        return ""
    # Μην αφαιρείς newlines, μόνο καθάρισε τα περιττά
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = re.sub(r"[ \t]+", " ", t)   # Καθάρισε διπλά κενά
    t = re.sub(r"\n{3,}", "\n\n", t)  # Μην αφήνεις πάνω από 2 συνεχόμενα newlines
    return t.strip()

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # Encode query
        q_emb = model.encode([f"query: {question}"], convert_to_numpy=True)
        q_emb = q_emb.astype('float32')
        faiss.normalize_L2(q_emb)

        # Αναζήτηση FAISS
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
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question, "matches": []}

        # Συγχώνευση chunks ανά ενότητα
        merged_by_section = {}
        for r in results:
            key = (r["filename"], r.get("section_idx"))
            merged_by_section.setdefault(key, {"chunks": [], "scores": []})
            merged_by_section[key]["chunks"].append((r["chunk_id"], r["text"]))
            merged_by_section[key]["scores"].append(r["score"])

        merged_list = sorted(merged_list, key=lambda x: x["score"], reverse=True)
        top_answers = merged_list[:TOP_K]

        answers_for_json = []
        for a in top_answers:
            text_with_source = f"{a['text']}\n\n📄 Πηγή: {a['filename']}\n📑 Section: {a.get('section_idx')} | Chunk: {a.get('chunk_id')}"
            answers_for_json.append({
                "text": text_with_source,
                "source": a['filename'],
                "section": a.get('section_idx'),
                "chunk_id": a.get('chunk_id')
            })

return {
    "answer": answers_for_json[0]["text"],  # η καλύτερη απάντηση ως main
    "query": question,
    "answers": answers_for_json
}

        # Join πίνακα όταν προηγείται αναφορά
        join_phrases = ["κάτωθι πίνακα", "ακόλουθο πίνακα", "βλέπε πίνακα", "παρακάτω πίνακα", "πίνακα:"]
        for i, m in enumerate(merged_list[:-1]):
            text_lower = m["text"].lower()
            next_chunk = merged_list[i + 1]["text"]
            if any(p in text_lower for p in join_phrases) and "📊 Πίνακας:" in next_chunk:
                merged_list[i]["text"] = m["text"].rstrip() + "\n\n" + next_chunk.strip()

        # Ταξινόμηση top 5
        merged_list = sorted(merged_list, key=lambda x: x["score"], reverse=True)
        top_answers = merged_list[:5]

        # Πρώτη απάντηση με ένδειξη πηγής
        best = top_answers[0]
        answer_text = f"📄 Πηγή: {best['filename']}\n\n{best['text']}"

        MAX_CHARS = 4000
        if len(answer_text) > MAX_CHARS:
            answer_text = answer_text[:MAX_CHARS].rsplit(' ', 1)[0] + " ..."

        return {
            "answer": answer_text,
            "source": best["filename"],
            "query": question,
            "matches": top_answers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
