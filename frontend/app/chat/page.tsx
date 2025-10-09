// frontend/app/chat/page.tsx
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "../api/auth/[...nextauth]/route";
import ChatClient from "./ChatClient";

export default async function ChatPage() {
  // Server-side session
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/login"); // Server-side redirect αν δεν υπάρχει session
  }

  return <ChatClient session={session} />;
}
