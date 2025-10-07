# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Αντιγράφουμε package.json και package-lock.json / yarn.lock
COPY package*.json ./

# Εγκατάσταση dependencies
RUN npm install

# Αντιγράφουμε όλο το υπόλοιπο app
COPY . .

# Build Next.js app
RUN npm run build

# Production image
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

# Αντιγράφουμε το build από το builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "start"]
