// frontend/app/api/ask/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { question } = await req.json();

  // Προσομοίωση απάντησης
  const answer = `You asked: "${question}"`;

  return NextResponse.json({ answer });
}
