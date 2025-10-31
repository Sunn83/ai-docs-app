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

CHUNK_SIZE = 350
CHUNK_OVERLAP = 50


# ✅ Μετατροπή πίνακα σε Markdown με wrap μεγάλων κελιών για ReactMarkdown
def table_to_markdown(table, wrap_length=80):
    """
    Μετατρέπει έναν DOCX πίνακα σε Markdown, σπάζοντας μεγάλα κελιά για ReactMarkdown.
    wrap_length: μέγιστος αριθμός χαρακτήρων ανά γραμμή κελιού
    """
    def wrap_text(text, max_length=wrap_length):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > max_length:
                lines.append(current)
                current = word
            else:
                current += (" " if current else "") + word
        if current:
            lines.append(current)
        return "<br>".join(lines)  # ReactMarkdown καταλαβαίνει <br> για newline

    rows_text = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = cell.text.strip()
            text = text.replace("\u00A0", " ").replace("\r", "").replace("\n", " ")
            text = wrap_text(text)
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

    return markdown_table

def read_docx_sections(filepath):
    """Διαβάζει DOCX και επιστρέφει λίστα ενοτήτων με πίνακες και τίτλους."""
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
            paragraph = doc.paragraphs[len([e for e in doc.element.body if e.tag.endswith('p')]) - len(doc.element.body) + list(doc.element.body).index(element)]
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
                table = [t for t in doc.tables][len([e for e in doc.element.body if e.tag.endswith("tbl")]) - len(sections) - 1]
            except Exception:
                continue
            if table:
                table_md = table_to_markdown(table)
                if table_md.strip():
                    # όταν διαβάζεις table_text:
                    print("📘 --- TABLE DEBUG ---")
                    print(table_md)
                    print("\n----------------------\n")
                    current_body.append(table_md)

    flush_section()

    if not sections:
        all_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        sections = [{"title": None, "text": all_text}]

    return sections


def chunk_section_text(section_text, max_words=400, overlap_words=60):
    """Σπάει ενότητες σε κομμάτια, κρατώντας προτάσεις ακέραιες."""
    if not section_text:
        return []

    sentences = re.split(r'(?<=[\.\!\?])\s+', section_text.strip())
    chunks, cur, cur_count = [], [], 0

    for s in sentences:
        words = s.split()
        wcount = len(words)
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

    return [c for c in chunks if len(c.split()) > 5]


def load_docs():
    """Φορτώνει όλα τα DOCX και φτιάχνει chunks με metadata."""
    metadata, all_chunks = [], []
    for fname in os.listdir(DOCS_PATH):
        if not fname.lower().endswith(".docx"):
            continue
        path = os.path.join(DOCS_PATH, fname)
        sections = read_docx_sections(path)
        for si, sec in enumerate(sections):
            sec_title = sec.get("title")
            sec_text = sec.get("text") or ""
            chunks = chunk_section_text(sec_text, max_words=CHUNK_SIZE, overlap_words=CHUNK_OVERLAP)
            if not chunks and sec_text.strip():
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


def create_faiss_index(embeddings):
    faiss.normalize_L2(embeddings)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


def main():
    print("📄 Φόρτωση DOCX αρχείων...")
    chunks, metadata = load_docs()
    print(f"➡️  Βρέθηκαν {len(chunks)} chunks προς επεξεργασία.")

    print("🔍 Φόρτωση μοντέλου embeddings...")
    model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

    print("\n==== SAMPLE METADATA (πρώτα 10) ====")
    for i, m in enumerate(metadata[:10]):
        print(f"[{i}] file={m['filename']} section_idx={m['section_idx']} chunk_id={m['chunk_id']}")
        print("TEXT PREVIEW:", m['text'][:200].replace("\n", " "))
        print("---")
    print("Σύνολο chunks:", len(metadata))

    print("🧠 Δημιουργία embeddings...")
    embeddings = model.encode(
        [f"passage: {c}" for c in chunks],
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype('float32')

    print("🔧 Δημιουργία FAISS index...")
    index = create_faiss_index(embeddings)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ Indexing ολοκληρώθηκε επιτυχώς!")


if __name__ == "__main__":
    main()
