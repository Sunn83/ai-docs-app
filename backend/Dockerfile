FROM python:3.10-slim

WORKDIR /app

COPY . /app

# 🧩 Εγκατάσταση system εργαλείων (curl + LibreOffice)
RUN apt-get update && \
    apt-get install -y curl libreoffice && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 📦 Εγκατάσταση Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn python-docx pydantic faiss-cpu sentence-transformers PyMuPDF

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
