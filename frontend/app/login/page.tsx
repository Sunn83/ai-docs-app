"use client";

export const dynamic = "force-dynamic";

import { useSearchParams } from "next/navigation";

export default function LoginPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  return (
    <div>
      {error && <p>Λάθος Στοιχεία</p>}
      {/* υπόλοιπο login form */}
    </div>
  );
}
