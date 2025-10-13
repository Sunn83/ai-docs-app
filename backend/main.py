from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from docx import Document

app = FastAPI()

# Επιτρέπουμε αιτήματα από το frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCS_PATH = "/data/docs"

@app.get("/")
def root():
    return {"message": "Backend is running!"}

def search_docs(query: str):
    results = []
    for filename in os.listdir(DOCS_PATH):
        if filename.endswith(".docx"):
            doc_path = os.path.join(DOCS_PATH, filename)
            doc = Document(doc_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            if query.lower() in text.lower():
                idx = text.lower().find(query.lower())
                start = max(idx - 50, 0)
                end = min(idx + 250, len(text))
                snippet = text[start:end]
                results.append(f"{filename}: ...{snippet}...")
    return "\n\n".join(results) if results else "Δεν βρέθηκαν σχετικά αποσπάσματα."

@app.post("/api/ask")
async def ask_question(request: Request):
    data = await request.json()
    question = data.get("question", "").strip()
    if not question:
        return {"answer": "Δεν δόθηκε ερώτημα."}
    
    answer = search_docs(question)
    return {"answer": answer}
