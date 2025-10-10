import NextAuth from "next-auth";
// Αν το authOptions.ts είναι στον ίδιο φάκελο
import { authOptions } from "./authOptions";


const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
