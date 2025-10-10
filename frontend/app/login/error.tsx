'use client';

export default function AuthError({ searchParams }: { searchParams: { error?: string } }) {
  const message = searchParams.error === "CredentialsSignin" ? "Λάθος Στοιχεία" : "Άγνωστο σφάλμα";

  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-2xl font-bold mb-4">Σφάλμα Σύνδεσης</h1>
      <p>{message}</p>
      <a href="/login" className="mt-4 text-blue-600 underline">Επιστροφή στη σύνδεση</a>
    </div>
  );
}
