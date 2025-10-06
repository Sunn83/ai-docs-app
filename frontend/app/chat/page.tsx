'use client';

import { useState } from "react";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [answers, setAnswers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question) return;

    setLoading(true);

    try {
      // Κάνουμε fetch στο proxy του Next.js, όχι απευθείας στο backend
      const res = await fetch(`/api/ask?q=${encodeURIComponent(question)}`);
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }

      const data = await res.json();

      // Αν το backend επιστρέφει text ή array, προσαρμόζουμε εδώ
      if (Array.isArray(data)) {
        setAnswers(data);
      } else if (data.answer) {
        setAnswers([data.answer]);
      } else {
        setAnswers([JSON.stringify(data)]);
      }

      setQuestion("");
    } catch (err: any) {
      console.error(err);
      setAnswers([`Error: ${err.message}`]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">AI Docs Chat</h1>

      <form onSubmit={handleSubmit} className="mb-4 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Type your question..."
          className="flex-1 p-2 border rounded"
        />
        <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-500 text-white rounded">
          {loading ? "Loading..." : "Ask"}
        </button>
      </form>

      <div className="space-y-2">
        {answers.map((ans, idx) => (
          <div key={idx} className="p-2 border rounded bg-gray-100">
            {ans}
          </div>
        ))}
      </div>
    </div>
  );
}
