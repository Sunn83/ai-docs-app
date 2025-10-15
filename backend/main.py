from fastapi import FastAPI
from pydantic import BaseModel
import os
from docx import Document
from transformers import pipeline

app = FastAPI()

DOCS_DIR = "/data/docs"

# -------------------------------
# Φόρτωση ελαφριού free LLM (CPU friendly)
# -------------------------------
print("Φόρτωση μοντέλου...")
qa_pipeline = pipeline("text2text-generation", model="google/flan-t5-base", device=-1)
print("Μοντέλο φορτώθηκε επιτυχώς ✅")

class Question(BaseModel):
    question: str

def search_docs(question: str, max_paragraphs: int = 5) -> str:
    """
    Αναζητά παραγράφους που περιέχουν την ερώτηση (keyword-based search).
    """
    results = []
    for file in os.listdir(DOCS_DIR):
        if file.endswith(".docx"):
            doc_path = os.path.join(DOCS_DIR, file)
            try:
                doc = Document(doc_path)
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    # Αναζήτηση με keyword
                    if any(word.lower() in text.lower() for word in question.split()):
                        results.append(text)
            except Exception as e:
                print(f"⚠️ Σφάλμα στην ανάγνωση {file}: {e}")

    if not results:
        return "Δεν βρέθηκαν σχετικά αποσπάσματα."
    return "\n".join(results[:max_paragraphs])

def generate_answer(context: str, question: str) -> str:
    """
    Δημιουργεί απάντηση βασισμένη μόνο στο context των docx.
    """
    prompt = f"Χρησιμοποίησε ΜΟΝΟ το παρακάτω κείμενο για να απαντήσεις:\n{context}\n\nΕρώτηση: {question}\nΑπάντησε στα ελληνικά σύντομα και με σαφήνεια."
    result = qa_pipeline(prompt, max_new_tokens=150)
    return result[0]['generated_text'].strip()

@app.post("/api/ask")
def ask_question(q: Question):
    context = search_docs(q.question)
    if "Δεν βρέθηκαν" in context:
        return {"answer": context}

    try:
        answer = generate_answer(context, q.question)
        return {"answer": answer}
    except Exception as e:
        print(f"Σφάλμα στο LLM: {e}")
        return {"answer": "Σφάλμα κατά την επεξεργασία της ερώτησης."}

@app.get("/")
def root():
    return {"message": "Backend is running ✅"}
