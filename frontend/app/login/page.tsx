"use client";

import { useSearchParams } from "next/navigation";

export default function LoginPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  const message =
    error === "CredentialsSignin"
      ? "Λάθος Στοιχεία"
      : error
      ? "Άγνωστο σφάλμα"
      : null;

  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-2xl font-bold mb-4">Σύνδεση</h1>
      {message && <p className="text-red-600 mb-4">{message}</p>}

      <form method="post" action="/api/auth/callback/credentials" className="flex flex-col gap-2 w-64">
        <input
          name="username"
          type="text"
          placeholder="Username"
          required
          className="p-2 border rounded"
        />
        <input
          name="password"
          type="password"
          placeholder="Password"
          required
          className="p-2 border rounded"
        />
        <button
          type="submit"
          className="mt-2 bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
        >
          Σύνδεση
        </button>
      </form>
    </div>
  );
}
