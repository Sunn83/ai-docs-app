# backend/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import requests
import os

app = FastAPI()

# Αν θέλεις να δέχεται requests από το frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ή ["http://localhost:3000"] για ασφάλεια
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Φόρτωση όλων των Word docs στο startup
DOCS_FOLDER = "data/docs"
docs_text = []

for filename in os.listdir(DOCS_FOLDER):
    if filename.endswith(".docx"):
        doc_path = os.path.join(DOCS_FOLDER, filename)
        doc = Document(doc_path)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        docs_text.append(full_text)

print(f"Φόρτωσα {len(docs_text)} αρχεία Word.")

@app.post("/api/ask")
async def ask(request: Request):
    try:
        data = await request.json()
        question = data.get("question", "").strip()
        if not question:
            return {"answer": "Δεν δόθηκε ερώτηση."}

        # Συνένωση όλων των docx σε context
        context = "\n\n".join(docs_text)

        # Prompt προς το Ollama LLM
        prompt = f"""
Χρησιμοποιώντας μόνο τα παρακάτω έγγραφα, απάντησε στην ερώτηση στα Ελληνικά:
{context}

Ερώτηση: {question}
Απάντηση:
"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral:latest",
                "prompt": prompt,
                "max_tokens": 300,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}

        # Συλλογή κειμένου από chunks
        result = response.json()
        answer = "".join([chunk.get("response", "") for chunk in result]) if isinstance(result, list) else result.get("response", "")

        if not answer.strip():
            answer = "Δεν βρέθηκε απάντηση στα αρχεία."

        return {"answer": answer}

    except Exception as e:
        print("Σφάλμα:", e)
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}
