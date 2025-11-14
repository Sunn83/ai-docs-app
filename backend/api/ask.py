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

# -------------------- Memory για follow-up --------------------
CHAT_HISTORY = []  # (role, text) tuples
MAX_HISTORY = 8

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

# -------------------- Build prompt για LLM --------------------
def build_prompt(history, user_message, context_chunks):
    history_text = ""
    for role, content in history:
        history_text += f"{role.upper()}: {content}\n"

    context_text = "\n\n---\n\n".join(context_chunks)

    return f"""
Σε αυτό το συνομιλητικό περιβάλλον είσαι νομικός βοηθός.
Ακολουθεί πλήρες ιστορικό συζήτησης:

{history_text}

---

Νέα ερώτηση χρήστη:
USER: {user_message}

---

Χρησιμοποίησε τις παρακάτω σχετικές πληροφορίες (RAG):
{context_text}

Οδηγίες:
- Αν η ερώτηση είναι follow-up, απάντησε λαμβάνοντας υπόψη το ιστορικό.
- Αν σου ζητηθεί "άλλο παράδειγμα", δώσε νέο παράδειγμα.
- Αν η ερώτηση έχει παραμέτρους, κάνε συλλογιστική και υπολόγισε το αποτέλεσμα.
- Αν δεν υπάρχει απάντηση στο context, απάντησε "δεν βρέθηκε πληροφορία".

Δώσε καθαρή, δομημένη και κατανοητή απάντηση.
"""

# -------------------- Endpoint --------------------
@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # 🔹 Encode query
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
                if text:
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
        context_chunks = [r["text"] for r in top_results]

        # 🔹 Φτιάχνουμε prompt με ιστορικό
        prompt = build_prompt(CHAT_HISTORY, question, context_chunks)

        # 🔹 Κλήση LLM (χρησιμοποίησε τη δική σου συνάρτηση που στέλνει prompt στο μοντέλο)
        # Για παράδειγμα: response_text = call_llm(prompt)
        response_text = "📝 Προσομοίωση απάντησης από LLM για παράδειγμα."  # αντικατάστησε με call_llm(prompt)

        # 🔹 Ενημέρωση memory
        CHAT_HISTORY.append(("user", question))
        CHAT_HISTORY.append(("assistant", response_text))
        if len(CHAT_HISTORY) > MAX_HISTORY:
            CHAT_HISTORY[:] = CHAT_HISTORY[-MAX_HISTORY:]

        # 🔹 Επιστροφή formatted απαντήσεων με PDF links
        answers = []
        for r in top_results:
            answer_text = clean_text(r["text"])
            filename_pdf = re.sub(r'\.docx?$', '.pdf', r["filename"], flags=re.IGNORECASE)
            encoded_filename = quote(filename_pdf)
            pdf_url = f"{PDF_BASE_URL}/{encoded_filename}#page={r['page']}"

            formatted = (
                f"{answer_text}\n\n"
                f"📄 Πηγή: [{r['filename']}]({pdf_url})\n"
                f"📑 Σελίδα: {r['page']}"
            )
            answers.append({"answer": formatted, "score": r["score"]})

        return {"answers": answers, "query": question, "llm_answer": response_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
