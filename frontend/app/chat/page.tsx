"use client";
import { useState } from "react";

export default function Page() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`/api/ask?q=${encodeURIComponent(query)}`, {
        method: "GET", // Μπορείς να βάλεις POST αν θέλεις
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      setAnswer("⚠️ Σφάλμα επικοινωνίας με τον server");
      console.error(err);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit">Ρώτα</button>
      </form>
      <p>{answer}</p>
    </div>
  );
}
