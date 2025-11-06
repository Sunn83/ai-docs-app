@router.post("/api/ask")
def ask(query: Query):
    try:
        question = query.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Άδεια ερώτηση.")

        # 🔹 Encode query
        q_emb = model.encode([f"query: {question}"], convert_to_numpy=True)
        q_emb = q_emb.astype('float32')
        faiss.normalize_L2(q_emb)

        # 🔹 Αναζήτηση FAISS
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
                    "page": md.get("section_idx"),   # section_idx -> page
                    "text": md.get("text")
                })

        if not results:
            return {"answer": "Δεν βρέθηκε σχετική απάντηση.", "source": None, "query": question}

        # 🔹 Συγχώνευση chunks ανά σελίδα
        merged_by_page = {}
        for r in results:
            key = (r["filename"], r.get("page"))
            merged_by_page.setdefault(key, {"chunks": [], "scores": []})
            merged_by_page[key]["chunks"].append((0, r["text"]))  # απλά για join
            merged_by_page[key]["scores"].append(r["score"])

        merged_list = []
        for (fname, page), val in merged_by_page.items():
            sorted_chunks = [t for _, t in sorted(val["chunks"], key=lambda x: x[0])]
            joined = "\n\n".join(sorted_chunks)
            avg_score = float(sum(val["scores"]) / len(val["scores"]))
            merged_list.append({
                "filename": fname,
                "page": page,
                "text": joined,
                "score": avg_score
            })

        merged_list = sorted(merged_list, key=lambda x: x["score"], reverse=True)
        best = merged_list[0]

        # ✨ Καθάρισμα κειμένου
        answer_text = clean_text(best["text"])

        # ✨ Προσθήκη πηγής και σελίδας στο τέλος
        answer_text += f"\n\n📄 Πηγή: {best['filename']}\n📑 Σελίδα: {best['page']}"

        MAX_CHARS = 4000
        if len(answer_text) > MAX_CHARS:
            answer_text = answer_text[:MAX_CHARS].rsplit(' ', 1)[0] + " ..."

        return {
            "answer": answer_text,
            "query": question
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
