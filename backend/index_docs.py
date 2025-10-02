import os, glob, pickle
import docx
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

DOCS_PATH = "/data/docs"
FAISS_INDEX = "/data/faiss.index"
DOCS_META = "/data/docs_meta.json"
CHUNK_SIZE = 500

model = SentenceTransformer("all-MiniLM-L6-v2")

docs_meta, embeddings = [], []

def read_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def chunk_text(text, size=CHUNK_SIZE):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size])

for file in glob.glob(os.path.join(DOCS_PATH, "*.docx")):
    content = read_docx(file)
    for chunk in chunk_text(content):
        emb = model.encode([chunk])[0]
        embeddings.append(emb)
        docs_meta.append({"text": chunk, "filename": os.path.basename(file)})

emb_matrix = np.array(embeddings).astype("float32")
index = faiss.IndexFlatL2(emb_matrix.shape[1])
index.add(emb_matrix)

faiss.write_index(index, FAISS_INDEX)
with open(DOCS_META, "wb") as f:
    pickle.dump(docs_meta, f)

print("✅ Index ολοκληρώθηκε")
