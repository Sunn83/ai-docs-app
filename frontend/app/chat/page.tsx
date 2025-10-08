'use client'
import { useState } from 'react'
import axios from 'axios'
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "../api/auth/[...nextauth]/route";

export default async function ChatPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-4">AI Chat</h1>
      {/* εδώ συνεχίζεται ο κώδικας του chat */}
    </div>
  );
}


export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<string[]>([])

  const ask = async () => {
    const res = await axios.post('/api/ask', { question: input })
    setMessages([...messages, `Ερώτηση: ${input}`, `Απάντηση: ${res.data.answer}`])
    setInput('')
  }

  return (
    <div className="p-10">
      <h1 className="text-2xl font-bold mb-6">AI Docs Chat</h1>
      <div className="space-y-2 mb-4">
        {messages.map((m, i) => (
          <p key={i} className="bg-gray-200 p-2 rounded">{m}</p>
        ))}
      </div>
      <div className="flex gap-2">
        <input className="border p-2 flex-grow" value={input} onChange={e => setInput(e.target.value)} />
        <button className="bg-green-500 text-white px-4 py-2 rounded" onClick={ask}>Ρώτα</button>
      </div>
    </div>
  )
}
