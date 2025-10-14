from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import os
from docx import Document

app = FastAPI()

DOCS_DIR = "/data/docs"

class Question(BaseModel):
    question: str

def search_docs(question: str) -> str:
    results = []
    for file in os.listdir(DOCS_DIR):
        if file.endswith(".docx"):
            doc = Document(os.path.join(DOCS_DIR, file))
            for para in doc.paragraphs:
                if question.lower() in para.text.lower():
                    results.append(para.text)
    return "\n".join(results) if results else "Δεν βρέθηκαν σχετικά αποσπάσματα."

@app.post("/api/ask")
def ask_question(q: Question):
    try:
        context = search_docs(q.question)
        if not context:
            return {"answer": "Δεν βρέθηκαν σχετικά αποσπάσματα."}

        # Κλήση ollama generate
        cmd = [
            "ollama",
            "generate",
            "-m", "mistral:latest",
            "--prompt", f"{context}\n\nΕρώτηση: {q.question}\nΑπάντησε στα ελληνικά:"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        answer = result.stdout.strip()
        return {"answer": answer}
    except Exception as e:
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}
