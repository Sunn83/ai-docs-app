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


# ✅ Μετατροπή πίνακα σε Markdown (χωρίς <br> και χωρίς σπασίματα)
def table_to_markdown(table):
    rows_text = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip()
            text = text.replace("\u00A0", " ").replace("\r", " ").replace("\n", " ")
            text = re.sub(r"\s{2,}", " ", text)
            cells.append(text)
        rows_text.append(" | ".join(cells))

    if not rows_text:
        return ""

    num_cols = rows_text[0].count("|") + 1
    separator = " | ".join(["---"] * num_cols)

    markdown_table = "\n".join([
        "",
        "📊 Πίνακας:",
        rows_text[0],
        separator,
        *rows_text[1:],
        ""
    ])

    # Καθάρισε πολλαπλά νέα κενά
    markdown_table = re.sub(r"\n{3,}", "\n\n", markdown_table)
    return markdown_table


def read_docx_sections(filepath):
    doc = Document(filepath)
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
        if element.tag.endswith("p"):
            paragraph = doc.paragraphs[
                len([e for e in doc.element.body if e.tag.endswith('p')])
                - len(doc.element.body)
                + list(doc.element.body).index(element)
            ]
            txt = paragraph.text.strip()
            if not txt:
                continue

            style_name = getattr(paragraph.style, "name", "").lower()
            if style_name.startswith("heading") or "επικεφαλίδα" in style_name:
                flush_section()
                current_title = txt
                current_body = []
                continue

            if re.match(r"^\s*(\d+(\.\d+)+|άρθρο\s+\d+|θέμα|ενότητα)", txt.lower()):
                flush_section()
                current_title = txt
                current_body = []
                continue

            current_body.append(txt)

        elif element.tag.endswith("tbl"):
            table = None
            try:
                table = [t for t in doc.tables][
                    len([e for e in doc.element.body if e.tag.endswith("tbl")])
                    - len(sections)
                    - 1
                ]
            except Exception:
                continue
            if table:
                table_md = table_to_markdown(table)
                if table_md.strip():
                    current_body.append(table_md)

    flush_section()

    if not sections:
        all_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]

    return sections

def chunk_section_text(section_text, max_words=400, overlap_words=60):
    """
    Σπάει section_text σε chunks, αλλά **δεν κόβει** μέσα σε markdown πίνακες.
    Εξάγει πρώτα κάθε '📊 Πίνακας:' block ως ξεχωριστό chunk.
    Το υπόλοιπο κείμενο σπάει σε chunks με βάση προτάσεις.
    """
    if not section_text:
        return []

    chunks = []
    # pattern που βρίσκει κάθε πίνακα που ξεκινά με "📊 Πίνακας:" έως πριν τον επόμενο ή EOF
    table_pattern = re.compile(r'📊 Πίνακας:\n.*?(?=(?:\n📊 Πίνακας:)|\Z)', re.S)

    cursor = 0
    for m in table_pattern.finditer(section_text):
        start, end = m.span()
        # κομμάτι πριν τον πίνακα -> το σπάμε
        pre = section_text[cursor:start].strip()
        if pre:
            # split σε προτάσεις και chunk
            sentences = re.split(r'(?<=[\.\!\?])\s+', pre)
            cur, cur_count = [], 0
            for s in sentences:
                wcount = len(s.split())
                if cur_count + wcount > max_words and cur:
                    chunks.append(" ".join(cur).strip())
                    tail = " ".join(" ".join(cur).split()[-overlap_words:])
                    cur = [tail, s]
                    cur_count = len(tail.split()) + wcount
                else:
                    cur.append(s)
                    cur_count += wcount
            if cur:
                chunks.append(" ".join(cur).strip())

        # ο ίδιος ο πίνακας -> προστίθεται **ολόκληρος** ως ένα chunk
        table_block = m.group(0).strip()
        if table_block:
            chunks.append(table_block)

        cursor = end

    # τυχόν υπόλοιπο μετά τον τελευταίο πίνακα
    tail = section_text[cursor:].strip()
    if tail:
        sentences = re.split(r'(?<=[\.\!\?])\s+', tail)
        cur, cur_count = [], 0
        for s in sentences:
            wcount = len(s.split())
            if cur_count + wcount > max_words and cur:
                chunks.append(" ".join(cur).strip())
                tail2 = " ".join(" ".join(cur).split()[-overlap_words:])
                cur = [tail2, s]
                cur_count = len(tail2.split()) + wcount
            else:
                cur.append(s)
                cur_count += wcount
        if cur:
            chunks.append(" ".join(cur).strip())

    # αφαιρούμε πολύ μικρά ή κενά
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
