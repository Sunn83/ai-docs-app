"use client";

import { useState } from "react";

export default function ChatClient() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");

    try {
      // Αλλαγή endpoint στο σωστό backend
      const res = await fetch("/api/ask", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input }), // σωστό πεδίο
      });

      const data = await res.json();

      const botMessage = { role: "bot", content: data.answer }; // backend επιστρέφει "answer"
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        { role: "bot", content: "Σφάλμα σύνδεσης με το server." },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-screen p-4 bg-gray-100">
      <div className="flex-1 overflow-y-auto mb-4 border rounded p-2 bg-white shadow">
        {messages.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "text-right text-blue-700" : "text-left text-gray-800"}
          >
            <strong>{m.role === "user" ? "Εσύ" : "Bot"}:</strong> {m.content}
          </div>
        ))}
      </div>

      <div className="flex">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          className="flex-1 border p-2 rounded"
          placeholder="Γράψε την ερώτησή σου..."
        />
        <button
          onClick={sendMessage}
          className="ml-2 p-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Στείλε
        </button>
      </div>
    </div>
  );
}
