# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import os
import ollama

app = FastAPI()

# Επιτρέπει requests από το frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Φορτώνει όλα τα Word docs στον φάκελο /data/docs
DOCS_PATH = "/data/docs"
documents = []

for filename in os.listdir(DOCS_PATH):
    if filename.endswith(".docx"):
        path = os.path.join(DOCS_PATH, filename)
        doc = Document(path)
        text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        documents.append(text)

@app.get("/")
def root():
    return {"message": "Backend is running with local LLM!"}

@app.post("/api/ask")
async def ask_question(request: Request):
    data = await request.json()
    question = data.get("question", "").strip()
    
    if not question:
        return {"answer": "Δεν δόθηκε ερώτηση."}

    # Συνενώνει όλα τα έγγραφα σε ένα string για context
    context = "\n".join(documents)
    
    # Δημιουργεί prompt για το local LLM
    prompt = f"Χρησιμοποίησε μόνο τα παρακάτω έγγραφα για να απαντήσεις στην ερώτηση:\n{context}\n\nΕρώτηση: {question}\nΑπάντηση:"

    try:
        # Κλήση στο Mistral local LLM μέσω ollama Python API
        response = ollama.chat(model="mistral:latest", messages=[{"role": "user", "content": prompt}])
        answer = response[0]["content"] if response else "Δεν βρέθηκε απάντηση."
    except Exception as e:
        print("LLM error:", e)
        answer = "Σφάλμα κατά την επεξεργασία της ερώτησης."

    return {"answer": answer}
