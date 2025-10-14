FROM python:3.10-slim

WORKDIR /app

COPY main.py /app/

RUN pip install --upgrade pip
RUN pip install fastapi uvicorn python-docx

# ollama πρέπει να είναι εγκατεστημένο στο host και διαθέσιμο στο container
RUN apt update && apt install -y snapd
RUN snap install ollama
ENV PATH="/snap/bin:$PATH"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
