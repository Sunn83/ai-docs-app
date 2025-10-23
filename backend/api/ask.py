# api/ask.py — ουσιαστικό μέρος
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import faiss, json, os
import numpy as np
from sentence_transformers import SentenceTransformer

router = APIRouter()
INDEX_FILE = "/data/faiss.index"
META_FILE = "/data/docs_meta.json"

model = SentenceTransformer("intfloat/multilingual-e5-base", cache_folder="/root/.cache/huggingface")

if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
    raise RuntimeError("❌ Δεν βρέθηκε FAISS index ή metadata.")

index = faiss.read_index(INDEX_FILE)
with open(META_FILE, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("✅ FAISS index και metadata φορτώθηκαν στη μνήμη.")

class Query(BaseModel):
    question: str

import re

@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        q_emb = model.encode(f"query: {question}", convert_to_numpy=True)
        q_emb = q_emb.astype('float32')
        faiss.normalize_L2(q_emb)

        k = 7
        D, I = index.search(q_emb, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            if idx < len(metadata):
                md = metadata[idx]
                results.append({
                    "idx": int(idx),
                    "score": float(score),
                    "filename": md["filename"],
                    "section_title": md.get("section_title"),
                    "section_idx": md.get("section_idx"),
                    "chunk_id": md.get("chunk_id"),
                    "text": md.get("text")
                })

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question}

        # sort by score desc
        results = sorted(results, key=lambda x: x["score"], reverse=True)

        # Merge chunks that come from same file & same section (ordered by chunk_id)
        merged_by_section = {}
        for r in results:
            key = (r["filename"], r.get("section_idx"))
            if key not in merged_by_section:
                merged_by_section[key] = {"chunks": [], "scores": []}
            merged_by_section[key]["chunks"].append((r["chunk_id"], r["text"]))
            merged_by_section[key]["scores"].append(r["score"])

        # For each section, sort chunks by chunk_id and join
        merged_list = []
        for (fname, sidx), val in merged_by_section.items():
            sorted_chunks = [t for _, t in sorted(val["chunks"], key=lambda x: (x[0] if x[0] is not None else 0))]
            joined = "\n\n".join(sorted_chunks)
            avg_score = float(sum(val["scores"]) / len(val["scores"]))
            merged_list.append({
                "filename": fname,
                "section_idx": sidx,
                "text": joined,
                "score": avg_score
            })

        # pick best merged section by score
        merged_list = sorted(merged_list, key=lambda x: x["score"], reverse=True)
        best = merged_list[0]

        # CLEANUP: remove duplicate heading repetitions like "2.4 ...\n2.4 ...", collapse repeated lines
        def clean_text(t):
            # 1) collapse multiple identical consecutive lines
            t = re.sub(r'(?m)^(?P<L>.+)\n(?P=L)(\n(?P=L))*', r'\g<L>', t)
            # 2) remove multiple occurrences of same heading repeated inside small window
            t = re.sub(r'(?s)(^.{0,200}?)(\n\1)+', r'\1', t)
            # 3) normalize spaces and newlines
            t = re.sub(r'\n{3,}', '\n\n', t)
            t = " ".join(t.split())
            return t

        answer_text = clean_text(best["text"])

        # Optionally, if you want the answer to be a single paragraph starting after the heading:
        # If section_title exists, remove a leading repeated title from answer_text
        if merged_list and merged_list[0].get("section_idx") is not None:
            title = None
            # find the metadata section title if present
            for md in metadata:
                if md["filename"] == best["filename"] and md.get("section_idx") == best["section_idx"]:
                    title = md.get("section_title")
                    break
            if title and answer_text.startswith(title):
                answer_text = answer_text[len(title):].lstrip(': ').lstrip()

        MAX_CHARS = 4000
        if len(answer_text) > MAX_CHARS:
            answer_text = answer_text[:MAX_CHARS].rsplit(' ', 1)[0] + " ..."

        return {
            "answer": answer_text,
            "source": best["filename"],
            "query": question,
            "matches": merged_list[:5]   # για debug στο frontend
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
