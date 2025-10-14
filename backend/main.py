from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
from docx import Document

app = FastAPI()

DOCS_DIR = "/data/docs"
OLLAMA_API_URL = "http://host.docker.internal:11434/api/generate"  # ή "http://172.17.0.1:11434/api/generate" αν δεν δουλεύει

class Question(BaseModel):
    question: str

def search_docs(question: str) -> str:
    """Αναζήτηση σε όλα τα .docx έγγραφα για σχετικό κείμενο"""
    results = []
    for file in os.listdir(DOCS_DIR):
        if file.endswith(".docx"):
            try:
                doc = Document(os.path.join(DOCS_DIR, file))
                for para in doc.paragraphs:
                    if question.lower() in para.text.lower():
                        results.append(para.text)
            except Exception as e:
                print(f"Σφάλμα ανάγνωσης {file}: {e}")
    return "\n".join(results) if results else ""

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.post("/api/ask")
def ask_question(q: Question):
    """Αποστολή ερώτησης προς το Ollama API με βάση τα δεδομένα των docx"""
    try:
        context = search_docs(q.question)
        if not context:
            return {"answer": "Δεν βρέθηκαν σχετικά αποσπάσματα στα έγγραφα."}

        prompt = f"""Χρησιμοποίησε το παρακάτω περιεχόμενο για να απαντήσεις στην ερώτηση.
Να απαντήσεις στα ελληνικά, με σαφήνεια και ακρίβεια.

Πλαίσιο:
{context}

Ερώτηση: {q.question}
Απάντηση:"""

        payload = {
            "model": "mistral:latest",
            "prompt": prompt
        }

        response = requests.post(OLLAMA_API_URL, json=payload, stream=True, timeout=120)
        response.raise_for_status()

        # Το Ollama στέλνει απαντήσεις σε ροή JSON γραμμή-γραμμή
        full_answer = ""
        for line in response.iter_lines():
            if not line:
                continue
            try:
                data = line.decode("utf-8")
                chunk = eval(data) if data.startswith("{") else None
                if chunk and "response" in chunk:
                    full_answer += chunk["response"]
            except Exception:
                continue

        if not full_answer.strip():
            full_answer = "Δεν υπήρξε απάντηση από το μοντέλο."

        return {"answer": full_answer.strip()}

    except requests.exceptions.RequestException as e:
        print(f"Σφάλμα Ollama API: {e}")
        return {"answer": "Σφάλμα επικοινωνίας με το Ollama API."}
    except Exception as e:
        print(f"Σφάλμα κατά την επεξεργασία: {e}")
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}
