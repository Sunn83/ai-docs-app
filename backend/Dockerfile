FROM python:3.10-slim

WORKDIR /app

# HuggingFace cache fix — ΑΠΑΡΑΙΤΗΤΟ για να μην ξανακατεβάζει το μοντέλο
ENV HF_HOME=/root/.cache/huggingface

# System dependencies (curl + libreoffice)
RUN apt-get update && \
    apt-get install -y curl libreoffice && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Dependencies (ΠΟΛΥ πιο σωστό έτσι)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy εφαρμογής
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
