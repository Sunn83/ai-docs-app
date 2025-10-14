"use client";

import { useState } from "react";

export default function ChatClient() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input }),
      });

      if (!res.ok) {
        const errText = await res.text();
        console.error("Server error:", errText);
        setMessages(prev => [
          ...prev,
          { role: "bot", content: "⚠️ Σφάλμα στον server. Δοκίμασε ξανά." },
        ]);
      } else {
        const data = await res.json();
        const botMessage = { role: "bot", content: data.answer || "Δεν ελήφθη απάντηση." };
        setMessages(prev => [...prev, botMessage]);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      setMessages(prev => [
        ...prev,
        { role: "bot", content: "⚠️ Αποτυχία σύνδεσης με το backend." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") sendMessage();
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 p-4">
      <div className="flex-1 overflow-y-auto mb-4 p-3 bg-white rounded-2xl shadow-inner border">
        {messages.length === 0 && (
          <p className="text-center text-gray-400 italic">Γράψε μια ερώτηση για να ξεκινήσεις...</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`my-2 p-2 rounded-xl ${
              m.role === "user"
                ? "bg-blue-100 text-right text-blue-900"
                : "bg-gray-200 text-left text-gray-800"
            }`}
          >
            <strong>{m.role === "user" ? "Εσύ" : "Bot"}:</strong> {m.content}
          </div>
        ))}
        {loading && <p className="text-sm text-gray-400 italic">⏳ Το μοντέλο σκέφτεται...</p>}
      </div>

      <div className="flex">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Γράψε την ερώτησή σου..."
          className="flex-1 border border-gray-300 rounded-xl p-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          onClick={sendMessage}
          disabled={loading}
          className={`ml-2 px-4 py-2 rounded-xl text-white ${
            loading ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          Στείλε
        </button>
      </div>
    </div>
  );
}
