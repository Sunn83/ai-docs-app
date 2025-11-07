from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.ask import router as ask_router
import os

# Δημιουργία εφαρμογής FastAPI
app = FastAPI(title="AI Docs API")

# CORS — επιτρέπει στο frontend να επικοινωνεί με το backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # μπορείς να βάλεις συγκεκριμένο domain αν θέλεις
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Mount του folder με PDF
PDF_FOLDER = "/data/pdfs"
os.makedirs(PDF_FOLDER, exist_ok=True)  # βεβαιώσου ότι υπάρχει ο φάκελος
app.mount("/pdf", StaticFiles(directory=PDF_FOLDER), name="pdf")

# Εγγραφή των routes από το api/ask.py
app.include_router(ask_router)

# Απλό route για έλεγχο ότι τρέχει
@app.get("/")
def root():
    return {"message": "AI Docs API is running!"}
