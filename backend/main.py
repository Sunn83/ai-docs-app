from fastapi import FastAPI

app = FastAPI()

@app.post("/api/ask")
async def ask(question: str):
    return {"answer": f"You asked: {question}"}
