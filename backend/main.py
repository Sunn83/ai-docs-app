from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
import subprocess
import os

app = FastAPI()

OLLAMA_URL = "http://ollama:11434/api/generate"
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

print("🔧 Φόρτωση FAISS index και metadata...")
index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)
texts = data["texts"]
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class Question(BaseModel):
    question: str

@app.post("/api/ask")
def ask_question(q: Question):
    question_emb = model.encode([q.question]).astype("float32")
    D, I = index.search(question_emb, 5)  # top 5 related paragraphs
    context = "\n".join([texts[i] for i in I[0]])

    payload = {
        "model": "mistral:latest",
        "prompt": f"Βασισμένος στα παρακάτω αποσπάσματα:\n{context}\n\nΕρώτηση: {q.question}\nΑπάντησε στα ελληνικά:"
    }

    cmd = [
        "curl", "-s", "-X", "POST", OLLAMA_URL,
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        resp_json = json.loads(result.stdout)
        answer = resp_json.get("response", "").strip()
    except:
        answer = "Σφάλμα στην επεξεργασία απάντησης από το Ollama."

    return {"answer": answer}
