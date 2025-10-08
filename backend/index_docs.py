import os

def reindex_docs():
    docs_path = os.getenv("DOCS_PATH", "./data/docs")
    files = os.listdir(docs_path)
    print(f"Βρέθηκαν {len(files)} έγγραφα για επεξεργασία.")
    return files

if __name__ == "__main__":
    reindex_docs()
