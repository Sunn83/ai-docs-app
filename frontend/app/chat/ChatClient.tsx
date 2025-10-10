"use client";

import { Session } from "next-auth";
import { useState } from "react";

interface ChatClientProps {
  session: Session;
}

export default function ChatClient({ session }: ChatClientProps) {
  const [messages, setMessages] = useState<string[]>([]);

  return (
    <div className="p-4">
      <h1 className="text-xl mb-2">Καλώς ήρθες, {session.user?.name || "χρήστη"}</h1>
      <div className="border p-2 rounded bg-gray-50">
        {messages.length === 0 ? (
          <p>Δεν υπάρχουν μηνύματα ακόμα.</p>
        ) : (
          messages.map((msg, i) => <p key={i}>{msg}</p>)
        )}
      </div>
    </div>
  );
}
