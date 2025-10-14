from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import ollama
import asyncio

app = FastAPI()

# CORS: επέτρεψε frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ή ["http://144.91.115.48:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Backend is running and connected to Ollama!"}

@app.post("/api/ask")
async def ask_question(request: Request):
    try:
        data = await request.json()
        question = data.get("question", "")

        if not question:
            return {"error": "Empty question"}

        # Σύνδεση με Ollama (local)
        response = ollama.chat(model="mistral:latest", messages=[
            {"role": "user", "content": question}
        ])

        answer = response["message"]["content"]
        return {"answer": answer}

    except Exception as e:
        print("❌ Error:", e)
        return {"error": "Σφάλμα κατά την επεξεργασία της ερώτησης."}
