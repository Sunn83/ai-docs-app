import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { question } = await req.json();

    // Κλήση στο backend container που τρέχει το local LLM
    const res = await fetch("http://144.91.115.48:8000/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("Backend error:", text);
      return NextResponse.json(
        { error: "Backend request failed" },
        { status: 500 }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);

  } catch (err) {
    console.error("API /ask error:", err);
    return NextResponse.json(
      { error: "Server error" },
      { status: 500 }
    );
  }
}
