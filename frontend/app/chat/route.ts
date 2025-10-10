import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { message } = await req.json();

  // Εδώ μπορείς να καλέσεις το backend ή το μοντέλο σου (faiss/ollama)
  // προσωρινά κάνουμε echo για να δούμε ότι δουλεύει
  const reply = `Απάντηση στο: "${message}"`;

  return NextResponse.json({ reply });
}
