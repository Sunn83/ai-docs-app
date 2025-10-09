# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Αντιγραφή μόνο των package.json για caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Αντιγραφή όλων των αρχείων του frontend
COPY frontend/ ./

# Build Next.js app
RUN npm run build

# ---------- Stage 2: Production ----------
FROM node:20-alpine AS runner

WORKDIR /app

# Αντιγραφή build και public folder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

# Install only production dependencies
RUN npm install --only=production --legacy-peer-deps

# Set environment
ENV NODE_ENV=production

# Expose port
EXPOSE 3000

# Start app
CMD ["npm", "start"]
