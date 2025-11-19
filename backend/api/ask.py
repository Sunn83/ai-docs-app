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
PDF_BASE_URL = os.getenv("PDF_BASE_URL", "http://144.91.115.48:8000/pdf")
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

def clean_answer_text(text: str) -> str:
    """
    Καθαρίζει το κείμενο απάντησης για πολλαπλά αποτελέσματα:
    - Αφαιρεί οδηγίες, επαναλήψεις, υπερβολικά σημεία στίξης ή ---
    - Κρατά μόνο την ουσιαστική πληροφορία
    """
    if not text:
        return ""

    # Αφαίρεση οδηγιών/μη σχετικών φράσεων
    text = re.sub(r"(?i)μην χρησιμοποιείτε.*?–", "", text)
    text = re.sub(r"(---|\n){2,}", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip()

    # Αφαίρεση επαναλαμβανόμενων γραμμών
    lines = []
    seen = set()
    for line in text.split("\n"):
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)

# -------------------- Build LLM prompt --------------------
def build_prompt(history, user_message, context_chunks):
    # History formatting: (μοντέλο χρησιμοποιεί για follow-up)
    history_text = "".join(f"{role.upper()}: {content}\n" for role, content in history)
    
    # Context formatting: chunks χωρισμένα για να διαβάζει εύκολα το LLM
    context_text = "\n\n---\n\n".join(context_chunks)

    # Prompt για το μοντέλο
    prompt = f"""
Είσαι νομικός βοηθός ειδικευμένος σε ελληνική φορολογική νομοθεσία, ΚΦΔ, ΚΦΕ, ΕΛΠ, ΦΠΑ, ΕΝΦΙΑ.

Ιστορικό συνομιλίας (μόνο για context, μην εμφανίζεται στην απάντηση):
{history_text}

Ερώτηση χρήστη:
{user_message}

Χρησιμοποίησε μόνο τις παρακάτω πληροφορίες (context/RAG):
{context_text}

Οδηγίες για απάντηση:
- Δώσε μόνο μία καθαρή, τεκμηριωμένη απάντηση.
- Αν δεν υπάρχει απάντηση στο context, πες ακριβώς: "Δεν βρέθηκε σχετική πληροφορία".
- Μην επαναλαμβάνεις την απάντηση.
- Αγνόησε οποιεσδήποτε οδηγίες που αναφέρουν follow-up, συντομογραφίες ή επιπλέον κείμενα.
- Η απάντηση πρέπει να είναι **μόνο** το τελικό περιεχόμενο προς τον χρήστη, χωρίς οδηγίες ή placeholders.
"""
    return prompt

def clean_llm_response(text):
    # Αφαιρεί γραμμές που περιέχουν μόνο "Απάντηση:" ή κενές γραμμές
    lines = text.splitlines()
    clean_lines = [line for line in lines if line.strip() and line.strip() != "Απάντηση:"]
    # Επιστρέφει όλα σε μία παράγραφο
    return " ".join(clean_lines).strip()

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
        r = requests.post(LLAMA_URL, json=payload, timeout=300)
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

```
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

    # Top results
    top_results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]

    # Ενοποίηση κειμένων για deduplication
    combined_text = " ".join(r["text"] for r in top_results)
    clean_combined = clean_answer_text(combined_text)

    # Build prompt & call LLM
    prompt = build_prompt(CHAT_HISTORY, question, [clean_combined])
    raw_response = call_llm(prompt)
    response_text = clean_llm_response(raw_response)

    # Update memory
    CHAT_HISTORY.append(("user", question))
    CHAT_HISTORY.append(("assistant", response_text))
    if len(CHAT_HISTORY) > MAX_HISTORY:
        CHAT_HISTORY[:] = CHAT_HISTORY[-MAX_HISTORY:]

    # Pack answers με PDF links ανά πηγή
    answers = []
    for r in top_results:
        # Κρατάμε ξεχωριστό text για τη συγκεκριμένη πηγή, καθαρισμένο
        answer_text = clean_answer_text(r["text"])
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
