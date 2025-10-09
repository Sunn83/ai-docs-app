// frontend/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import { authOptions } from "../authOptions";

// Δημιουργούμε τον handler με βάση τα authOptions
const handler = NextAuth(authOptions);

// Εξάγουμε τον handler για όλα τα HTTP methods που χρειάζεται NextAuth
export { handler as GET, handler as POST };
