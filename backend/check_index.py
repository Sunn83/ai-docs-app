import faiss
import pickle

# Φόρτωσε FAISS index
index_path = "/data/faiss.index"  # αν χρειάζεται, άλλαξε path
index = faiss.read_index(index_path)
print("Number of vectors in FAISS index:", index.ntotal)

# Φόρτωσε metadata (πιθανώς pickle)
meta_path = "/data/docs_meta.json"  # αν χρειάζεται, άλλαξε path
with open(meta_path, "rb") as f:  # rb για binary pickle
    docs_meta = pickle.load(f)

print("\nDocs indexed:")
for doc in docs_meta:
    print("-", doc)
