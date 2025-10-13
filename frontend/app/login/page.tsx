"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const params = useSearchParams();
  const token = params.get("token");

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="p-8 bg-gray-100 rounded-xl shadow-md">
        <h1 className="text-2xl font-semibold mb-4">Login</h1>
        <p>Token: {token ?? "No token provided"}</p>
      </div>
    </div>
  );
}
