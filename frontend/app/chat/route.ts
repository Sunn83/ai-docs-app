import { NextRequest, NextResponse } from "next/server";
import { queryDocs } from "../../../lib/faiss";

export async function POST(req: NextRequest) {
  try {
    const { message } = await req.json();
    const reply = await queryDocs(message);
    return NextResponse.json({ reply });
  } catch (error) {
    console.error("API /chat error:", error);
    return NextResponse.json({ reply: "Σφάλμα στον server." }, { status: 500 });
  }
}
