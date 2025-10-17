from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import pipeline

router = APIRouter()

INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

# Φόρτωση FAISS και metadata
if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ FAISS ή metadata αρχείο δεν βρέθηκαν στο /data.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS και metadata φορτώθηκαν στη μνήμη.")

# Φόρτωση embedding και summarization μοντέλων
print("🔍 Φόρτωση μοντέλων (embeddings + summarizer)...")
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

class Query(BaseModel):
    question: str

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # Μετατροπή της ερώτησης σε embedding
        q_emb = embedder.encode([question])
        q_emb = np.array(q_emb).astype("float32")

        # Αναζήτηση στα FAISS embeddings (top 3 πιο σχετικά)
        D, I = index.search(q_emb, k=3)

        results = []
        full_text = ""

        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                chunk = metadata[idx]
                results.append({
                    "filename": chunk["filename"],
                    "text": chunk["text"],
                    "distance": float(score)
                })
                full_text += chunk["text"] + " "

        # Δημιουργία σύνοψης
        summary = "Δεν βρέθηκε σχετική απάντηση."
        if full_text.strip():
            summary_raw = summarizer(full_text[:1500], max_length=80, min_length=20, do_sample=False)
            summary = summary_raw[0]["summary_text"]

        # Επιστροφή απάντησης και αναφορών
        top_doc = results[0]["filename"] if results else "Άγνωστο"

        return {
            "question": question,
            "answer": summary,
            "source": top_doc,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
