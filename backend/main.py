from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import os
from docx import Document

app = FastAPI()

# Φάκελος με τα docx αρχεία
DOCS_DIR = "/data/docs"

# IP του host όπου τρέχει ο Ollama
OLLAMA_HOST = "172.17.0.1"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"

class Question(BaseModel):
    question: str

def search_docs(question: str) -> str:
    """
    Αναζητά την ερώτηση μέσα στα docx αρχεία και επιστρέφει τα σχετικά αποσπάσματα.
    """
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
    """
    Δέχεται ερώτηση, αναζητά context στα docs και επιστρέφει απάντηση από το Ollama.
    """
    try:
        context = search_docs(q.question)
        if not context:
            return {"answer": "Δεν βρέθηκαν σχετικά αποσπάσματα."}

        # Δημιουργία payload για Ollama API
        payload = {
            "model": "mistral:latest",
            "prompt": f"{context}\n\nΕρώτηση: {q.question}\nΑπάντησε στα ελληνικά:"
        }

        # Κλήση Ollama API μέσω curl
        cmd = [
            "curl",
            "-s",
            "-X", "POST",
            OLLAMA_URL,
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Επεξεργασία απάντησης
        try:
            response_json = json.loads(result.stdout)
            answer = response_json.get("response", "").strip()
            if not answer:
                answer = "Δεν βρέθηκε απάντηση από το Ollama."
        except json.JSONDecodeError:
            answer = "Σφάλμα στην επεξεργασία της απάντησης από το Ollama."

        return {"answer": answer}

    except Exception as e:
        print(f"Σφάλμα: {e}")
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}

@app.get("/")
def root():
    return {"message": "Backend is running"}
