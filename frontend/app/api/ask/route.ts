import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { question } = await req.json();

    if (!question || !question.trim()) {
      return NextResponse.json({ answer: "Παρακαλώ δώσε μια ερώτηση." });
    }

    // Κλήση στο backend container
    const res = await fetch("http://ai-docs-app-backend:8000/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("Backend error:", text);
      return NextResponse.json({ answer: "Σφάλμα από το backend." });
    }

    const data = await res.json();
    return NextResponse.json({ answer: data.answer });

  } catch (err) {
    console.error("API /ask error:", err);
    return NextResponse.json({ answer: "Σφάλμα σύνδεσης με το server." });
  }
}
