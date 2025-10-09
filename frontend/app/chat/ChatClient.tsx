"use client";

import { useState } from "react";
import axios from "axios";

export default function ChatClient({ session }: { session: any }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<string[]>([]);

  const ask = async () => {
    try {
      const res = await axios.post("/api/ask", { question: input });
      setMessages([...messages, `Ερώτηση: ${input}`, `Απάντηση: ${res.data.answer}`]);
      setInput("");
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-10">
      <h1 className="text-2xl font-bold mb-6">AI Docs Chat</h1>
      <div className="space-y-2 mb-4">
        {messages.map((m, i) => (
          <p key={i} className="bg-gray-200 p-2 rounded">
            {m}
          </p>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="border p-2 flex-grow"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="bg-green-500 text-white px-4 py-2 rounded" onClick={ask}>
          Ρώτα
        </button>
      </div>
    </div>
  );
}
