from fastapi import FastAPI, Query
from sentence_transformers import SentenceTransformer
import faiss
import json
import pickle

app = FastAPI()

# Load model και index
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
index = faiss.read_index("/data/faiss.index")

# Load metadata (pickle format)
with open("/data/docs_meta.json", "rb") as f:
    docs_meta = pickle.load(f)

@app.get("/api/ask")
def ask(q: str = Query(..., min_length=1)):
    try:
        print("Received query:", q)
        q_vec = model.encode([q], convert_to_numpy=True)
        D, I = index.search(q_vec, k=5)
        print("Indices found:", I)
        print("Distances:", D)

        results = []
        for idx in I[0]:
            if idx < len(docs_meta):
                chunk = docs_meta[idx]
                print("Using chunk from file:", chunk.get("filename"))
                results.append({
                    "text": chunk.get("text"),
                    "source": chunk.get("filename")
                })
            else:
                print("Index out of range:", idx)

        if not results:
            print("No results found for query.")
        return {"answer": results}
    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}
