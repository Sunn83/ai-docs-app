"use client"; // Αυτό χρειάζεται για Next.js App Router για state/hooks
import { useState } from "react";

interface Result {
  text: string;
  source: string;
}

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);

    try {
      const res = await fetch(`/api/ask?q=${encodeURIComponent(query)}`);
      const data = await res.json();

      if (data.answer) {
        setResults(data.answer);
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error("Error fetching results:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "2rem auto", padding: "1rem" }}>
      <h1>AI Chat</h1>

      <form onSubmit={handleSubmit} style={{ marginBottom: "1rem" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Γράψε την ερώτησή σου..."
          style={{ width: "70%", padding: "0.5rem", fontSize: "1rem" }}
        />
        <button type="submit" style={{ padding: "0.5rem 1rem", marginLeft: "1rem" }}>
          Ρώτησε
        </button>
      </form>

      {loading && <p>Φόρτωση αποτελεσμάτων...</p>}

      <div>
        {results.map((r, i) => (
          <div key={i} style={{ border: "1px solid #ccc", padding: "1rem", marginBottom: "1rem" }}>
            <p>{r.text}</p>
            <small>Πηγή: {r.source}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
