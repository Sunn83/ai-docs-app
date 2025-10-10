import CredentialsProvider from "next-auth/providers/credentials";
import { NextAuthOptions } from "next-auth";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Όνομα χρήστη", type: "text" },
        password: { label: "Κωδικός", type: "password" },
      },
      async authorize(credentials) {
        const username = process.env.NEXTAUTH_USERNAME;
        const password = process.env.NEXTAUTH_PASSWORD;

        if (
          credentials?.username === username &&
          credentials?.password === password
        ) {
          return { id: "1", name: username };
        }
        return null; // Λάθος στοιχεία → redirect στο /login?error=CredentialsSignin
      },
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
};
