from fastapi import FastAPI
from pydantic import BaseModel
import json
import os
from docx import Document
import requests

app = FastAPI()

DOCS_DIR = "/data/docs"
OLLAMA_URL = "http://ollama:11434/api/generate"

class Question(BaseModel):
    question: str

def search_docs(question: str) -> str:
    results = []
    for file in os.listdir(DOCS_DIR):
        if file.endswith(".docx"):
            doc_path = os.path.join(DOCS_DIR, file)
            try:
                doc = Document(doc_path)
                for para in doc.paragraphs:
                    if question.lower() in para.text.lower():
                        results.append(para.text)
            except Exception as e:
                print(f"Σφάλμα στην ανάγνωση {file}: {e}")
    return "\n".join(results) if results else "Δεν βρέθηκαν σχετικά αποσπάσματα."

@app.post("/api/ask")
def ask_question(q: Question):
    try:
        context = search_docs(q.question)
        if not context:
            return {"answer": "Δεν βρέθηκαν σχετικά αποσπάσματα."}

        payload = {
            "model": "mistral:latest",
            "prompt": f"{context}\n\nΕρώτηση: {q.question}\nΑπάντησε στα ελληνικά:"
        }

        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=20)
            r.raise_for_status()
            response_json = r.json()
            answer = response_json.get("response", "").strip()
            if not answer:
                answer = "Δεν βρέθηκε απάντηση από το Ollama."
        except Exception as e:
            answer = f"Σφάλμα επικοινωνίας με το Ollama API: {e}"

        return {"answer": answer}

    except Exception as e:
        print(f"Σφάλμα: {e}")
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}

@app.get("/")
def root():
    return {"message": "Backend is running"}
