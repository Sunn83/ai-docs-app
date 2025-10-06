"use client";

import { useState } from "react";
import axios from "axios";
import MessageBubble from "../../components/MessageBubble";

export default function ChatPage() {
  const [messages, setMessages] = useState<{ text: string; sender: string; sources?: string[] }[]>([]);
  const [input, setInput] = useState("");

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMsg = { text: input, sender: "user" };
    setMessages([...messages, newMsg]);

    setInput("");
    const res = await axios.get("/api/ask", { params: { q: input } });

    setMessages((prev) => [
      ...prev,
      { text: res.data.answer, sender: "ai", sources: res.data.sources },
    ]);
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} text={msg.text} sender={msg.sender} sources={msg.sources} />
        ))}
      </div>
      <div className="p-4 border-t flex">
        <input
          className="flex-1 p-2 border rounded mr-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <button onClick={sendMessage} className="bg-blue-500 text-white px-4 rounded">
          Send
        </button>
      </div>
    </div>
  );
}
