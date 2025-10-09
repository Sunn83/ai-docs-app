// frontend/app/chat/ChatClient.tsx
"use client";

import { useState } from "react";
import axios from "axios";

interface ChatClientProps {
  session: any;
}

export default function ChatClient({ session }: ChatClientProps) {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState("");

  const ask = async () => {
    if (!input.trim()) return;

    try {
      const res = await axios.post("/api/ask", { question: input });
      setMessages(prev => [
        ...prev,
        `Ερώτηση: ${input}`,
        `Απάντηση: ${res.data.answer}`,
      ]);
      setInput("");
    } catch (err) {
      console.error("Error sending question:", err);
    }
  };

  return (
    <div>
      <h1>Welcome, {session.user.name}</h1>

      <div>
        {messages.map((msg, i) => (
          <p key={i}>{msg}</p>
        ))}
      </div>

      <input
        type="text"
        value={input}
        onChange={e => setInput(e.target.value)}
        placeholder="Type your question..."
      />
      <button onClick={ask}>Send</button>
    </div>
  );
}
