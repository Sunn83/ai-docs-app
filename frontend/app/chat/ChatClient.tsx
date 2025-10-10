'use client';

import { Session } from "next-auth";

interface ChatClientProps {
  session: Session;
}

export default function ChatClient({ session }: ChatClientProps) {
  return (
    <div className="p-4">
      <h1 className="text-xl font-bold">Καλώς ήρθες, {session.user?.name}</h1>
      <p>Εδώ θα εμφανίζεται το chat.</p>
    </div>
  );
}
