#!/bin/bash

# Όνομα backend container (όπως στο docker-compose.yml)
CONTAINER="ai-docs-app-backend"

# Έλεγχος αν τρέχει το container
if [ "$(docker ps -q -f name=$CONTAINER)" == "" ]; then
  echo "❌ Δεν βρέθηκε backend container. Τρέξε πρώτα: docker compose up -d"
  exit 1
fi

echo "📂 Δημιουργία νέου FAISS index στο container: $CONTAINER"
docker exec -it "$CONTAINER" python3 /app/reindex.py
echo "✅ Reindex ολοκληρώθηκε επιτυχώς!"
