"use client";

import { useState } from "react";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answers, setAnswers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setAnswers([]);

    try {
      const res = await fetch(
        `http://144.91.115.48:8000/api/ask?q=${encodeURIComponent(question)}`
      );

      if (!res.ok) {
        throw new Error(`Server responded with status ${res.status}`);
      }

      const data = await res.json();

      // Αν η απάντηση έρχεται ως array από objects με text:
      const texts = data.answer?.map((a: any) => a.text) || [];
      setAnswers(texts);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">AI Docs Chat</h1>

      <form onSubmit={handleSubmit} className="mb-4">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Γράψε την ερώτησή σου..."
          className="border p-2 w-full rounded mb-2"
        />
        <button
          type="submit"
          className="bg-blue-500 text-white px-4 py-2 rounded"
          disabled={loading}
        >
          {loading ? "Στέλνεται..." : "Ρώτησε"}
        </button>
      </form>

      {error && <p className="text-red-500 mb-4">{error}</p>}

      {answers.length > 0 && (
        <div className="space-y-2">
          {answers.map((text, i) => (
            <div
              key={i}
              className="border p-2 rounded bg-gray-100"
            >
              {text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
