# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder

# Ο φάκελος εργασίας μέσα στο container
WORKDIR /app

# Αντιγράφουμε τα αρχεία package.json και package-lock.json από το frontend
COPY frontend/package*.json ./

# Εγκατάσταση dependencies (συμπεριλαμβανομένου του axios και next-auth)
RUN npm install --legacy-peer-deps

# Αντιγραφή όλων των υπόλοιπων αρχείων του frontend
COPY frontend/. .

# Δημιουργία production build
RUN npm run build

# ---------- Stage 2: Production ----------
FROM node:20-alpine AS runner

WORKDIR /app

# Αντιγραφή μόνο όσων χρειάζονται από το προηγούμενο στάδιο
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

# Εγκατάσταση μόνο production dependencies
RUN npm install --only=production --legacy-peer-deps

ENV NODE_ENV=production

EXPOSE 3000

# Εκκίνηση του Next.js server
CMD ["npm", "start"]
