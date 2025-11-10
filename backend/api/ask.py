from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os, re
import numpy as np
from sentence_transformers import SentenceTransformer
from urllib.parse import quote

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"
PDF_BASE_URL = "http://144.91.115.48:8000/pdf"  # σωστό path για PDFs

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

def clean_text(t: str) -> str:
    """Καθαρισμός κειμένου, διατηρεί newlines"""
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

        # 🔹 Encode query (χωρίς "query: ")
        q_emb = model.encode([question], convert_to_numpy=True)
        q_emb = q_emb.astype("float32")
        faiss.normalize_L2(q_emb)

        # 🔹 Αναζήτηση FAISS
        k = 10
        D, I = index.search(q_emb, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                md = metadata[idx]
                text = md.get("text", "").strip()
                if text:  # ✅ Αγνοούμε κενά chunks
                    results.append({
                        "idx": int(idx),
                        "score": float(score),
                        "filename": md.get("filename", "unknown.pdf"),
                        "page": md.get("page", 1),
                        "text": text
                    })

        if not results:
            return {"answers": [{"answer": "Δεν βρέθηκε σχετική απάντηση.", "score": 0}], "query": question}

        # 🔹 Κράτα τις 3 καλύτερες απαντήσεις
        top_results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]

        answers = []
        for r in top_results:
            answer_text = clean_text(r["text"])
            filename_pdf = re.sub(r'\.docx?$', '.pdf', r["filename"], flags=re.IGNORECASE)
            # encoded_filename = quote(r["filename"])
            encoded_filename = quote(filename_pdf)
            pdf_url = f"{PDF_BASE_URL}/{encoded_filename}#page={r['page']}"

            formatted = (
                f"{answer_text}\n\n"
                f"📄 Πηγή: [{r['filename']}]({pdf_url})\n"
                f"📑 Σελίδα: {r['page']}"
            )

            answers.append({
                "answer": formatted,
                "score": r["score"]
            })

        return {"answers": answers, "query": question}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
