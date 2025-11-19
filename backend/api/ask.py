from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import faiss, json, os, re
import numpy as np
from sentence_transformers import SentenceTransformer
from urllib.parse import quote
import requests

# -------------------- FastAPI App & CORS --------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://144.91.115.48:3000"],  # frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

# -------------------- Files & URLs --------------------
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"
PDF_BASE_URL = os.getenv("PDF_BASE_URL", "http://backend:8000/pdf")
LLAMA_URL = "http://llama:8080/v1/completions"

# -------------------- Load Model & Index --------------------
model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ Δεν βρέθηκε FAISS index ή metadata.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS index και metadata φορτώθηκαν στη μνήμη.")

# -------------------- Memory για follow-up --------------------
CHAT_HISTORY = []
MAX_HISTORY = 8

class Query(BaseModel):
    question: str

# -------------------- Utility: Clean text --------------------
def clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

# -------------------- Build LLM prompt --------------------
def build_prompt(history, user_message, context_chunks):
    history_text = "".join(f"{role.upper()}: {content}\n" for role, content in history)
    context_text = "\n\n---\n\n".join(context_chunks)

    return f"""
Σε αυτό το συνομιλητικό περιβάλλον είσαι νομικός βοηθός ειδικευμένος σε Φορολογική νομοθεσία, ΚΦΔ, ΚΦΕ και ΕΛΠ.

Ακολουθεί ιστορικό συζήτησης:
{history_text}

---

Ερώτηση χρήστη:
USER: {user_message}

---

Χρησιμοποίησε τις παρακάτω σχετικές πληροφορίες (RAG):
{context_text}

Οδηγίες:
- Αν η ερώτηση είναι follow-up, λάβε υπόψη το ιστορικό.
- Αν δεν υπάρχει απάντηση στο context, πες «Δεν βρέθηκε σχετική πληροφορία».
- Δώσε καθαρή, δομημένη και τεκμηριωμένη απάντηση.
"""

# -------------------- LLM call --------------------
def call_llm(prompt: str) -> str:
    payload = {
        "model": "local",
        "prompt": prompt,
        "max_tokens": 512,
        "temperature": 0.2,
        "stop": ["USER:", "ASSISTANT:"]
    }

    try:
        r = requests.post(LLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["text"].strip()
    except Exception as e:
        return f"⚠ Σφάλμα από το LLM: {str(e)}"

# -------------------- API Endpoint --------------------
@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # Encode Query
        q_emb = model.encode([question], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(q_emb)

        # FAISS Search
        k = 10
        D, I = index.search(q_emb, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                md = metadata[idx]
                text = md.get("text", "").strip()
                if text:
                    results.append({
                        "idx": int(idx),
                        "score": float(score),
                        "filename": md.get("filename", "unknown.pdf"),
                        "page": md.get("page", 1),
                        "text": text
                    })

        if not results:
            return {"answers": [{"answer": "Δεν βρέθηκε σχετική απάντηση.", "score": 0}]}

        top_results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]
        context_chunks = [r["text"] for r in top_results]

        # Build prompt & call LLM
        prompt = build_prompt(CHAT_HISTORY, question, context_chunks)
        response_text = call_llm(prompt)

        # Update memory
        CHAT_HISTORY.append(("user", question))
        CHAT_HISTORY.append(("assistant", response_text))
        if len(CHAT_HISTORY) > MAX_HISTORY:
            CHAT_HISTORY[:] = CHAT_HISTORY[-MAX_HISTORY:]

        # Pack answers with PDF links
        answers = []
        for r in top_results:
            answer_text = clean_text(r["text"])
            filename_pdf = re.sub(r"\.docx?$", ".pdf", r["filename"], flags=re.IGNORECASE)
            encoded_filename = quote(filename_pdf)
            pdf_url = f"{PDF_BASE_URL}/{encoded_filename}#page={r['page']}"

            formatted = (
                f"{answer_text}\n\n"
                f"📄 Πηγή: [{r['filename']}]({pdf_url})\n"
                f"📑 Σελίδα: {r['page']}"
            )
            answers.append({"answer": formatted, "score": r["score"]})

        return {
            "answers": answers,
            "query": question,
            "llm_answer": response_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------- Include router in app --------------------
app.include_router(router)
