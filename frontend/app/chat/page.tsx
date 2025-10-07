"use client";

import { useState } from "react";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`/api/ask?q=${encodeURIComponent(question)}`);
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      console.error(err);
      setAnswer("Σφάλμα κατά την αναζήτηση.");
    }
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h1>AI Docs Chat</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ρώτα κάτι..."
          style={{ width: "300px", padding: "0.5rem" }}
        />
        <button type="submit" style={{ marginLeft: "1rem", padding: "0.5rem" }}>
          Στείλε
        </button>
      </form>
      {answer && <p style={{ marginTop: "1rem" }}><strong>Απάντηση:</strong> {answer}</p>}
    </div>
  );
}
