import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from docx import Document

DOCS_PATH = "/data/docs"
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

def extract_text_from_docx(path):
    """Διαβάζει το docx και επιστρέφει όλο το κείμενο σε string."""
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def reindex_docs():
    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    if not os.path.exists(DOCS_PATH):
        print(f"❌ Ο φάκελος {DOCS_PATH} δεν υπάρχει.")
        return

    files = [f for f in os.listdir(DOCS_PATH) if f.endswith(".docx")]
    print(f"📄 Βρέθηκαν {len(files)} αρχεία για επεξεργασία.")

    if not files:
        print("⚠️ Δεν υπάρχουν αρχεία για ευρετηρίαση.")
        return

    texts, meta = [], []
    for filename in files:
        full_path = os.path.join(DOCS_PATH, filename)
        print(f"📘 Επεξεργασία: {filename}")
        try:
            text = extract_text_from_docx(full_path)
            if text.strip():
                texts.append(text)
                meta.append({"filename": filename, "path": full_path})
            else:
                print(f"⚠️ Το αρχείο {filename} είναι κενό.")
        except Exception as e:
            print(f"❌ Σφάλμα στο {filename}: {e}")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode(texts, convert_to_numpy=True)

    print("💾 Δημιουργία FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, INDEX_FILE)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"✅ Το FAISS index αποθηκεύτηκε στο: {INDEX_FILE}")
    print(f"✅ Τα metadata αποθηκεύτηκαν στο: {META_FILE}")
    print("🎉 Επανευρετηρίαση ολοκληρώθηκε με επιτυχία!")

if __name__ == "__main__":
    reindex_docs()
