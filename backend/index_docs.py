import os
import faiss
import pickle
from docx import Document
from sentence_transformers import SentenceTransformer

# Ρυθμίσεις
DOCS_PATH = "/data/docs/"
INDEX_PATH = "/data/faiss.index"
META_PATH = "/data/docs_meta.pkl"
CHUNK_SIZE = 500  # λέξεις ανά chunk

# Φόρτωσε μοντέλο για embeddings
model = SentenceTransformer("all-MiniLM-L6-v2")  # μικρό & γρήγορο μοντέλο

# Συλλογή κειμένων
chunks = []
docs_meta = []

for filename in os.listdir(DOCS_PATH):
    if not filename.endswith(".docx"):
        continue
    filepath = os.path.join(DOCS_PATH, filename)
    doc = Document(filepath)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    
    words = full_text.split()
    for i in range(0, len(words), CHUNK_SIZE):
        chunk_text = " ".join(words[i:i+CHUNK_SIZE])
        if chunk_text.strip():
            chunks.append(chunk_text)
            docs_meta.append({"text": chunk_text, "filename": filename})

# Δημιουργία embeddings
embeddings = model.encode(chunks, convert_to_numpy=True)

# Δημιουργία FAISS index
dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(embeddings)

# Αποθήκευση
faiss.write_index(index, INDEX_PATH)
with open(META_PATH, "wb") as f:
    pickle.dump(docs_meta, f)

print(f"Indexing done! {len(chunks)} chunks from {len(set([d['filename'] for d in docs_meta]))} files.")
