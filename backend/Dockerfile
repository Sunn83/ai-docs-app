FROM python:3.10-slim

WORKDIR /app
COPY main.py /app/

RUN apt-get update && \
    apt-get install -y curl && \
    pip install --no-cache-dir fastapi uvicorn python-docx pydantic transformers torch sentencepiece && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
