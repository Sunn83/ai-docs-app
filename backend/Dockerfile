FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN apt-get update && \
    apt-get install -y curl && \
    pip install --no-cache-dir fastapi uvicorn python-docx pydantic faiss-cpu sentence-transformers && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
