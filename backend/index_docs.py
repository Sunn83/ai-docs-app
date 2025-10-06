import os

DATA_DIR = "/data"  # Ο φάκελος όπου βάζεις τα .docx

# Λίστα για να κρατάμε τα indexed docs
INDEX = []

def index_all_documents():
    global INDEX
    INDEX = []
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    for file in os.listdir(DATA_DIR):
        if file.endswith(".docx"):
            INDEX.append({"source": file, "text": f"Κείμενο από {file}"})
    print("✅ Indexing complete")

def search_documents(query: str):
    # Πολύ απλή αναζήτηση: επιστρέφει όλα τα docs που περιέχουν το query στο text
    results = [doc for doc in INDEX if query.lower() in doc["text"].lower()]
    return results
