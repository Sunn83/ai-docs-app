"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import ChatClient from "./ChatClient";
import { useEffect } from "react";

export default function ChatPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return <p>Φόρτωση...</p>;
  }

  if (!session) {
    return null; // μην αποδίδεις τίποτα αν δεν υπάρχει session
  }

  return <ChatClient session={session} />;
}
