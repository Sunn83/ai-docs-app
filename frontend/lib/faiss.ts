export async function queryDocs(question: string): Promise<string> {
  try {
    // Στέλνει το ερώτημα στο backend API που έχεις
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok) {
      console.error("FAISS backend error:", await res.text());
      return "Σφάλμα στο backend.";
    }

    const data = await res.json();
    return data.answer || "Δεν βρέθηκε απάντηση.";
  } catch (err) {
    console.error("Σφάλμα στο queryDocs:", err);
    return "Σφάλμα σύνδεσης με backend.";
  }
}
