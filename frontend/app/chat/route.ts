import { NextRequest, NextResponse } from "next/server";

// Προσωρινά fake απάντηση – αργότερα συνδέουμε FAISS/Ollama
export async function POST(req: NextRequest) {
  const { message } = await req.json();

  // TODO: αντικατάστησε με κλήση σε backend/ollama/faiss
  const reply = `Απάντηση στο: "${message}"`;

  return NextResponse.json({ reply });
}
