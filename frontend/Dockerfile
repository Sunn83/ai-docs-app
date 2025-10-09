# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Αντιγραφή μόνο των package files για caching
COPY package*.json ./

# Εγκατάσταση dependencies
RUN npm install --legacy-peer-deps

# Αντιγραφή όλων των υπολοίπων αρχείων του frontend
COPY . .

# Build Next.js app
RUN npm run build

# ---------- Stage 2: Production ----------
FROM node:20-alpine AS runner

WORKDIR /app

# Αντιγραφή απαραίτητων φακέλων από builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

# Εγκατάσταση μόνο production dependencies
RUN npm install --only=production --legacy-peer-deps

ENV NODE_ENV=production

EXPOSE 3000

CMD ["npm", "start"]
