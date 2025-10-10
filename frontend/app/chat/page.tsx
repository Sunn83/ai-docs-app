"use client";

import { useSession } from "next-auth/react";
import ChatClient from './ChatClient';

export default function ChatPage() {
  const { data: session } = useSession();

  if (!session) return <p>Σύνδεση απαιτείται</p>;

  return <ChatClient session={session} />;
}
