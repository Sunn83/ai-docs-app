'use client';

import { useSession } from "next-auth/react";
import ChatClient from "../chat/ChatClient";

export default function ChatPage() {
  const { data: session } = useSession();

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-screen">
        <p>Πρέπει να συνδεθείς για να δεις το chat.</p>
        <a href="/login" className="text-blue-600 underline mt-2">
          Πήγαινε στη σύνδεση
        </a>
      </div>
    );
  }

  return <ChatClient session={session} />;
}
