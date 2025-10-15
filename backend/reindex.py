from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from docx import Document
import os
import json

DOCS_DIR = "/data/docs"
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

print("🔍 Φόρτωση μοντέλου embeddings...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

texts = []
metadata = []

print("📄 Επεξεργασία αρχείων Word...")
for file in os.listdir(DOCS_DIR):
    if file.endswith(".docx"):
        path = os.path.join(DOCS_DIR, file)
        try:
            doc = Document(path)
            for i, para in enumerate(doc.paragraphs):
                if para.text.strip():
                    texts.append(para.text.strip())
                    metadata.append({"file": file, "paragraph": i})
        except Exception as e:
            print(f"Σφάλμα στο {file}: {e}")

print(f"🧠 Δημιουργία embeddings για {len(texts)} παραγράφους...")
embeddings = model.encode(texts, show_progress_bar=True)
embeddings = np.array(embeddings).astype("float32")

print("💾 Δημιουργία FAISS index...")
index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings)
faiss.write_index(index, INDEX_FILE)

print("📁 Αποθήκευση metadata...")
with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump({"texts": texts, "metadata": metadata}, f, ensure_ascii=False, indent=2)

print("✅ Ολοκληρώθηκε η δημιουργία του FAISS index!")
