"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect στον chat page
    router.push("/chat");
  }, [router]);

  return <p>Redirecting to chat...</p>;
}
