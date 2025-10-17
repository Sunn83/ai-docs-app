from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.ask import router as ask_router

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

# Εγγραφή των routes από το api/ask.py
app.include_router(ask_router)

# Απλό route για έλεγχο ότι τρέχει
@app.get("/")
def root():
    return {"message": "AI Docs API is running!"}
