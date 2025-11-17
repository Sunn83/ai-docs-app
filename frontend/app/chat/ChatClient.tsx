"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = {
  role: "user" | "assistant";
  content: string[]; // πάντα array για tabs
  activeTab: number; // ποιο tab εμφανίζεται
};

export default function ChatClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    // Προσθήκη μηνύματος χρήστη
    const userMessage: Message = { role: "user", content: [input], activeTab: 0 };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(process.env.NEXT_PUBLIC_API_URL + "/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input }),
      });

      const data = await res.json();
      const answers: string[] = data.answers?.map((a: any) => a.answer) || [
        "⚠️ Δεν βρέθηκαν απαντήσεις."
      ];

      const botMessage: Message = { role: "assistant", content: answers, activeTab: 0 };
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      const botMessage: Message = {
        role: "assistant",
        content: ["⚠️ Σφάλμα κατά τη λήψη απάντησης."],
        activeTab: 0,
      };
      setMessages(prev => [...prev, botMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading) {
      e.preventDefault();
      sendMessage();
    }
  };

  const setTab = (msgIndex: number, tabIndex: number) => {
    setMessages(prev =>
      prev.map((m, i) => (i === msgIndex ? { ...m, activeTab: tabIndex } : m))
    );
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-6">
      <div className="w-full max-w-2xl bg-white shadow-lg rounded-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-500 text-white p-4 font-semibold text-lg flex items-center justify-center">
          💼 ASTbooks — Έξυπνος Βοηθός
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] p-3 rounded-2xl shadow-sm whitespace-pre-line ${
                  m.role === "user"
                    ? "bg-blue-100 text-blue-900 rounded-br-none"
                    : "bg-gray-100 text-gray-800 rounded-bl-none"
                }`}
              >
                <strong className="block mb-1 text-sm opacity-70">
                  {m.role === "user" ? "Εσύ" : "ASTbooks"}
                </strong>

                {/* Tabs */}
                {m.content.length > 1 && (
                  <div className="flex space-x-2 mb-2">
                    {m.content.map((_, idx) => (
                      <button
                        key={idx}
                        onClick={() => setTab(i, idx)}
                        className={`px-3 py-1 rounded-xl text-sm ${
                          m.activeTab === idx
                            ? "bg-blue-600 text-white"
                            : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        Απάντηση {idx + 1}
                      </button>
                    ))}
                  </div>
                )}

                {/* Active answer */}
                <div className="prose prose-sm max-w-none break-words whitespace-pre-wrap text-justify leading-relaxed">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ node, href, children, ...props }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "blue" }}
                        {...props}
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {m.content[m.activeTab]}
                </ReactMarkdown>
                  </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 p-3 rounded-2xl rounded-bl-none shadow-sm text-gray-500 italic">
                ✨ Η ASTbooks σκέφτεται...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 p-4 flex items-center bg-gray-50">
          <input
            type="text"
            placeholder="Γράψε την ερώτησή σου..."
            className="flex-1 border border-gray-300 rounded-xl px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
          />
          <button
            onClick={sendMessage}
            disabled={loading}
            className="ml-3 px-5 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition disabled:opacity-50"
          >
            Αποστολή
          </button>
        </div>
      </div>
    </div>
  );
}
