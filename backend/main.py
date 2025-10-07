from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ CORS ενεργοποιημένο
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # μπορείς να βάλεις συγκεκριμένο domain π.χ. ["http://144.91.115.48"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/ask")
async def ask(q: str = Query(...)):
    return {"answer": f"Η ερώτηση ήταν: {q}"}
