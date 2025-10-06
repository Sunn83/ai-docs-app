import os
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from index_docs import index_all_documents, search_documents

app = FastAPI(title="AI Docs App")

# Δρομολογούμε το frontend μόνο αν υπάρχει
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# API για αναζήτηση
@app.get("/api/ask")
def ask(q: str = Query(..., min_length=1)):
    results = search_documents(q)
    return {"answer": results}

# Προαιρετικά: endpoint για reindex
@app.post("/api/reindex")
def reindex():
    index_all_documents()
    return {"status": "✅ Indexing complete"}
