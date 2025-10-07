from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # για testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GET endpoint
@app.get("/api/ask")
async def ask_get(q: str = Query(...)):
    return {"answer": f"You asked (GET): {q}"}

# POST endpoint
@app.post("/api/ask")
async def ask_post(payload: dict):
    query = payload.get("query")
    return {"answer": f"You asked (POST): {query}"}
