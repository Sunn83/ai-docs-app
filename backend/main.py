from fastapi import FastAPI, Query
import os, subprocess, pickle, numpy as np, faiss
from sentence_transformers import SentenceTransformer

app = FastAPI()

DOCS_PATH = os.getenv("DOCS_PATH", "/data/docs")
FAISS_INDEX = os.getenv("FAISS_INDEX", "/data/faiss.index")
DOCS_META = os.getenv("DOCS_META", "/data/docs_meta.json")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

model = SentenceTransformer("all-MiniLM-L6-v2")

try:
    index = faiss.read_index(FAISS_INDEX)
    with open(DOCS_META, "rb") as f:
        docs_meta = pickle.load(f)
except:
    index = None
    docs_meta = []

@app.get("/ask")
def ask(q: str = Query(...)):
    if not index:
        return {"answer": "⚠️ Δεν υπάρχει index", "sources": []}

    q_emb = model.encode([q])
    D, I = index.search(np.array(q_emb, dtype=np.float32), k=3)

    sources, context_chunks = [], []
    for i in I[0]:
        context_chunks.append(docs_meta[i]["text"])
        sources.append(docs_meta[i]["filename"])

    context = "\n".join(context_chunks)
    prompt = f"Χρησιμοποίησε το παρακάτω context:\n{context}\n\nΕρώτηση: {q}\nΑπάντησε στα ελληνικά:"

    ollama_res = subprocess.check_output(["ollama", "run", OLLAMA_MODEL], input=prompt.encode())
    return {"answer": ollama_res.decode(), "sources": sources}
