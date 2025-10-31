"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = {
  role: "user" | "assistant";
  content: string;
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

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input }),
      });

      const data = await res.json();

      console.log("API response:", data); // 🔹 Δες τι γυρίζει το backend στο browser console

      const botMessage: Message = {
        role: "assistant",
        content: data.answer || "⚠️ Δεν βρέθηκε απάντηση.",
      };

      // 🔹 Debug mode — δείξε τα matches ως collapsible JSON block
      if (data.matches && data.matches.length > 0) {
        const debugMsg: Message = {
          role: "assistant",
          content: "DEBUG_MATCHES:\n" + JSON.stringify(data.matches, null, 2),
        };
        setMessages((prev) => [...prev, botMessage, debugMsg]);
      } else {
        setMessages((prev) => [...prev, botMessage]);
      }

    } catch (err) {
      const errorMsg: Message = {
        role: "assistant",
        content: "⚠️ Σφάλμα κατά τη λήψη απάντησης.",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading) sendMessage();
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-6">
      <div className="w-full max-w-2xl bg-white shadow-lg rounded-2xl flex flex-col overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-500 text-white p-4 font-semibold text-lg text-center">
          💼 ASTbooks — Έξυπνος Βοηθός
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] p-3 rounded-2xl shadow-sm ${
                  m.role === "user"
                    ? "bg-blue-100 text-blue-900 rounded-br-none"
                    : "bg-gray-100 text-gray-800 rounded-bl-none"
                }`}
              >
                <strong className="block mb-1 text-sm opacity-70">
                  {m.role === "user" ? "Εσύ" : "ASTbooks"}
                </strong>

                {/* ✅ Εδώ η διορθωμένη δομή */}
                <div className="prose prose-sm max-w-none break-words whitespace-pre-wrap">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ ...props }) => (
                        <div className="overflow-x-auto my-4">
                          <table
                            className="table-auto border-collapse border border-gray-400 w-full text-sm"
                            {...props}
                          />
                        </div>
                      ),
                      th: ({ ...props }) => (
                        <th
                          className="border border-gray-400 bg-gray-100 px-2 py-1 text-left"
                          {...props}
                        />
                      ),
                      td: ({ ...props }) => (
                        <td className="border border-gray-400 px-2 py-1 align-top" {...props} />
                      ),
                    }}
                  >
                    {m.content}
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
          {/* 🔍 TEST: Markdown table rendering */}
        <div className="p-4 bg-gray-50 rounded-lg my-4">
          <h2 className="font-bold text-gray-700 mb-2">Test Markdown Table</h2>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {`| Εταιρεία | Τύπος | Πλήθος |
        | --- | --- | --- |
        | ΟΕ | Προσωπική | 100 |
        | ΕΠΕ | Κεφαλαιουχική | 200 |
        | ΙΚΕ | Ιδιωτική | 300 |`}
            </ReactMarkdown>
          </div>
        </div>
        </div>
        {/* 🔍 TEST: Markdown table rendering */}
        <div className="p-4 bg-gray-50 rounded-lg my-4">
          <h2 className="font-bold text-gray-700 mb-2">Test Markdown Table</h2>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {`| Εταιρεία | Τύπος | Πλήθος |
        | --- | --- | --- |
        | ΟΕ | Προσωπική | 100 |
        | ΕΠΕ | Κεφαλαιουχική | 200 |
        | ΙΚΕ | Ιδιωτική | 300 |`}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
