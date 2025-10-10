// frontend/app/chat/page.tsx
"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import ChatClient from "./ChatClient";

export default function ChatPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return <div className="p-8 text-center">Φόρτωση...</div>;
  }

  if (!session) {
    return null;
  }

  return <ChatClient />;
}
