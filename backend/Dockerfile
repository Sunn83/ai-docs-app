FROM python:3.10-slim

WORKDIR /app

COPY main.py /app/

RUN pip install --upgrade pip

# Εγκαθιστούμε όλα τα απαραίτητα πακέτα
RUN pip install fastapi uvicorn python-docx requests

# ollama πρέπει να είναι εγκατεστημένο στο host και διαθέσιμο στο container
ENV PATH="/snap/bin:$PATH"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
