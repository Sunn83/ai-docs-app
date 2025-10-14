FROM python:3.10-slim

WORKDIR /app

COPY main.py /app/

# Εγκαθιστούμε όλα τα απαραίτητα πακέτα
RUN pip install --upgrade pip && \
    pip install fastapi uvicorn python-docx requests

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
