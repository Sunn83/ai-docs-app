from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ή ["http://144.91.115.48:3000"] για πιο ασφαλές
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static frontend (αν θέλεις να εξυπηρετεί FastAPI)
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend/out")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# Fake search endpoint για δοκιμή
@app.get("/api/ask")
def ask(q: str = Query(...)):
    # Σύνδεση με faiss/index docs μπορεί να μπει εδώ
    return {"question": q, "answer": f"Απάντηση για: {q}"}
