# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Αντιγραφή package.json για caching
COPY package*.json ./

# Εγκατάσταση dependencies
RUN npm install --legacy-peer-deps

# Αντιγραφή υπόλοιπων αρχείων
COPY . .

# Δημιουργία production build
RUN npm run build

# ---------- Stage 2: Production ----------
FROM node:20-alpine AS runner

WORKDIR /app

# Αντιγραφή build
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

# Εγκατάσταση μόνο production dependencies
RUN npm install --only=production --legacy-peer-deps

ENV NODE_ENV=production

EXPOSE 3000

CMD ["npm", "start"]
