"use client";

import { useState } from "react";
import axios from "axios";
import MessageBubble from "../../components/MessageBubble";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<
    { text: string; sender: "user" | "ai"; sources?: string[] }[]
  >([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input) return;
    // Προσθέτουμε το μήνυμα του χρήστη
    setMessages((prev) => [...prev, { text: input, sender: "user" }]);
    setLoading(true);
    try {
      const res = await axios.post("http://backend:8000/ask", {
        question: input,
      });
      const answer = res.data.answer;
      const sources = res.data.sources; // αν το backend επιστρέφει πηγές
      setMessages((prev) => [...prev, { text: answer, sender: "ai", sources }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { text: "Error getting answer from backend", sender: "ai" },
      ]);
    } finally {
      setLoading(false);
      setInput("");
    }
  };

  return (
    <div className="p-4 flex flex-col h-screen max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">AI Docs Chat</h1>
      <div className="flex-1 overflow-auto mb-4 flex flex-col">
        {messages.map((msg, i) => (
          <MessageBubble key={i} text={msg.text} sender={msg.sender} sources={msg.sources} />
        ))}
      </div>
      <div className="flex">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 border p-2 rounded-l"
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          className="bg-blue-500 text-white p-2 rounded-r"
          disabled={loading}
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
