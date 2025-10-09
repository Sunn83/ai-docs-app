import { getServerSession } from "next-auth";
import { authOptions } from "../api/auth/[...nextauth]/route";
import ChatClient from "./ChatClient";

export default async function ChatPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    // Redirect σε login
    redirect("/login");
  }

  // Μόνο render της Client Component
  return <ChatClient session={session} />;
}
