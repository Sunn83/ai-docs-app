from fastapi import FastAPI, Query
from sentence_transformers import SentenceTransformer
import faiss
import json
import os
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Load model και index
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
index = faiss.read_index("/data/faiss.index")

# Load metadata
with open("/data/docs_meta.json", "r", encoding="utf-8") as f:
    docs_meta = json.load(f)

# Προσπάθεια να σερβιριστεί το frontend μόνο αν υπάρχει
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"Frontend folder not found at {frontend_path}. Serving API only.")

@app.get("/api/ask")
def ask(q: str = Query(..., min_length=1)):
    try:
        print("Received query:", q)
        q_vec = model.encode([q], convert_to_numpy_
