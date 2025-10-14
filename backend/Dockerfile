# Base image με Python 3.10 slim
FROM python:3.10-slim

# Ορισμός working directory
WORKDIR /app

# Αντιγραφή του main.py στο container
COPY main.py /app/

# Εγκατάσταση dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    pip install --no-cache-dir fastapi uvicorn python-docx pydantic && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Έκθεση του port 8000
EXPOSE 8000

# Εκκίνηση του backend με uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
