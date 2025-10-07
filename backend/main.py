from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AskRequest(BaseModel):
    question: str

@app.post("/api/ask")
async def ask(req: AskRequest):
    # προσωρινή απάντηση
    return {"answer": f"Echo: {req.question}"}

@app.get("/api/ask")
async def get_ask():
    return {"message": "Send POST request with JSON {'question': '...'}"}
