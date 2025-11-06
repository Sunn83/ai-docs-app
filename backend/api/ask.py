from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os, re
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
print("✅ FAISS index και metadata φορτώθηκαν.")

class Query(BaseModel):
    question: str


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

        q_emb = model.encode([f"query: {question}"], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(q_emb)
        k = 10
        D, I = index.search(q_emb, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                md = metadata[idx]
                results.append({**md, "score": float(score)})

        if not results:
            return {"answers": ["Δεν βρέθηκε σχετική απάντηση."], "sources": []}

        # top 3 απαντήσεις
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]

        answers, sources = [], []
        for r in results:
            text = clean_text(r["text"])
            pdf_url = r.get("pdf_url")
            page = r.get("page", 1)
            if pdf_url:
                link = f'<a href="{pdf_url}#page={page}" target="_blank">📄 Προβολή πλήρους κειμένου</a>'
            else:
                link = f"Πηγή: {r['filename']}"
            answers.append(f"{text}\n\n---\n\n{link}")
            sources.append({"filename": r["filename"], "page": page, "pdf": pdf_url})

        return {"answers": answers, "sources": sources, "query": question}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
