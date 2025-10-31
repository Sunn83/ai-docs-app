# backend/index_docs.py
import os
import json
from pathlib import Path
from docx import Document
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import re

DATA_DIR = "/data"
DOCS_PATH = os.path.join(DATA_DIR, "docs")
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
META_FILE = os.path.join(DATA_DIR, "docs_meta.json")

# Ρυθμίσεις chunking
CHUNK_SIZE = 350  # λέξεις ανά chunk
CHUNK_OVERLAP = 50  # επικάλυψη

# --- section-aware reading & chunking (βάλε στο backend/index_docs.py) ---

def read_docx_sections(file_path):
    """
    Διαβάζει DOCX και επιστρέφει sections:
    {"title": τίτλος ή None, "text": καθαρό κείμενο + πίνακες}

    ➤ Υποστηρίζει ελληνικές επικεφαλίδες ("Επικεφαλίδα", "Άρθρο", "Θέμα" κ.λπ.)
    ➤ Περιλαμβάνει και πίνακες (tables)
    """
    doc = Document(file_path)
    sections = []
    current_title = None
    current_body = []

    def flush_section():
        if not current_title and not current_body:
            return
        text = "\n".join([t.strip() for t in current_body if t.strip()])
        sections.append({
            "title": current_title.strip() if current_title else None,
            "text": text.strip()
        })

    for element in doc.element.body:
        # Paragraph
        if element.tag.endswith("p"):
            p = element
            paragraph = doc.paragraphs[len(sections) + len(current_body)] if len(doc.paragraphs) > len(sections) + len(current_body) else None
            if not paragraph:
                continue
            txt = paragraph.text.strip()
            if not txt:
                continue

            style_name = getattr(paragraph.style, "name", "").lower()
            if style_name.startswith("heading") or "επικεφαλίδα" in style_name:
                flush_section()
                current_title = txt
                current_body = []
                continue

            # Fallback τίτλοι (π.χ. "2.4 ...", "Άρθρο 5:", "Θέμα:")
            if re.match(r"^\s*(\d+(\.\d+)+|άρθρο\s+\d+|θέμα|ενότητα)", txt.lower()):
                flush_section()
                current_title = txt
                current_body = []
                continue

            current_body.append(txt)

        # Table
        elif element.tag.endswith("tbl"):
            table = doc.tables[len([e for e in doc.element.body if e.tag.endswith('tbl')]) - len(sections)]
            rows_text = []
            for row in table.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                rows_text.append(" | ".join(cells))

            # Αν υπάρχει header row, πρόσθεσε γραμμή διαχωρισμού --- για markdown πίνακα
            if rows_text:
                header = rows_text[0]
                cols = header.count("|") + 1
                separator = " | ".join(["---"] * cols)
                table_text = "\n".join(["", header, separator] + rows_text[1:] + [""])
                table_text = "📊 Πίνακας:\n" + table_text
                current_body.append(table_text)

    # flush τελευταίο section
    flush_section()

    # Αν δεν βρέθηκε τίποτα, βάλε ολόκληρο το doc σαν ένα section
    if not sections:
        all_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]

    return sections

def chunk_section_text(section_text, max_words=400, overlap_words=60):
    """
    Με βάση λέξεις - σπάει τη section σε chunks, κρατώντας sentences ακέραιες.
    Επιστρέφει λίστα chunk strings.
    """
    if not section_text:
        return []

    # split σε προτάσεις (βασικά με ., ?, ! αλλά διατηρούμε ελληνικά)
    sentences = re.split(r'(?<=[\.\!\?])\s+', section_text.strip())
    chunks = []
    cur = []
    cur_count = 0

    for s in sentences:
        words = s.split()
        wcount = len(words)
        if cur_count + wcount > max_words and cur:
            chunks.append(" ".join(cur).strip())
            # overlap: keep last overlap_words words from cur
            tail = " ".join(" ".join(cur).split()[-overlap_words:])
            cur = [tail, s]
            cur_count = len(tail.split()) + wcount
        else:
            cur.append(s)
            cur_count += wcount

    if cur:
        chunks.append(" ".join(cur).strip())

    # dedupe empty and very short
    chunks = [c for c in chunks if len(c.split()) > 5]
    return chunks

def load_docs():
    """
    Επιστρέφει: chunks_list, metadata_list (ordered lists)
    metadata entries: {"filename": fname, "section_title": title, "section_idx": i_section, "chunk_id": j_chunk}
    """
    metadata = []
    all_chunks = []
    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            # split section to chunks
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks:
                # if section was too small, keep whole section text
                if sec_text.strip():
                    chunks = [sec_text.strip()]
            for cj, chunk in enumerate(chunks):
                metadata.append({
                    "filename": fname,
                    "section_title": sec_title,
                    "section_idx": si,
                    "chunk_id": cj,
                    "text": chunk
                })
                all_chunks.append(chunk)
    return all_chunks, metadata


def split_by_headings(text):
    """
    Σπάει το docx σε ενότητες με βάση επικεφαλίδες τύπου '2.4 ...' ή 'Άρθρο ...'
    """
    # Κανονική έκφραση που εντοπίζει επικεφαλίδες (π.χ. 2.4, 3.1, Άρθρο 5, Θέμα)
    pattern = re.compile(r'(?=\n?\s*(?:\d+\.\d+|Άρθρο\s+\d+|Θέμα|Ενότητα)\b)', re.IGNORECASE)
    parts = pattern.split(text)
    return [p.strip() for p in parts if len(p.strip()) > 50]  # αγνόησε πολύ μικρά

def create_faiss_index(embeddings):
    # normalize για cosine similarity
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # inner product (cosine if normalized)
    index.add(embeddings)
    return index

def main():
    print("📄 Φόρτωση DOCX αρχείων...")
    chunks, metadata = load_docs()
    print(f"➡️  Βρέθηκαν {len(chunks)} chunks προς επεξεργασία.")

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode(
    [f"passage: {c}" for c in chunks],
    convert_to_numpy=True,
    show_progress_bar=True
    )

    # convert to float32 if όχι ήδη
    embeddings = embeddings.astype('float32')

    print("🔧 Κανονικοποίηση embeddings (L2) + δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    main()
