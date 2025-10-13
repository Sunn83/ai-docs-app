// frontend/app/api/chat/route.ts
import { NextRequest, NextResponse } from "next/server";
import { queryDocs } from "../../../lib/faiss"; // παράδειγμα

export async function POST(req: NextRequest) {
  const { message } = await req.json();

  // Παίρνουμε απάντηση από FAISS/Ollama
  const reply = await queryDocs(message);

  return NextResponse.json({ reply });
}
