"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import ChatClient from "./ChatClient";

export default function ChatPage() {
  // Χρησιμοποιούμε το useSession ΜΟΝΟ σε client περιβάλλον
  const sessionData = useSession();
  const router = useRouter();

  // Αν δεν υπάρχει session, redirect στο /login
  useEffect(() => {
    if (sessionData?.status === "unauthenticated") {
      router.push("/login");
    }
  }, [sessionData?.status, router]);

  if (sessionData?.status === "loading") {
    return <p>Φόρτωση...</p>;
  }

  if (!sessionData?.data) {
    return null;
  }

  return <ChatClient session={sessionData.data} />;
}

// ⚠️ Προσθέτουμε αυτό για να μη γίνεται prerender κατά το build
export const dynamic = "force-dynamic";
