#!/bin/bash

# Βρες αυτόματα το όνομα του backend container
CONTAINER=$(docker ps --filter "name=backend" --format "{{.Names}}" | head -n 1)

if [ -z "$CONTAINER" ]; then
  echo "❌ Δεν βρέθηκε backend container. Βεβαιώσου ότι τρέχει με: docker compose up -d"
  exit 1
fi

echo "📂 Τρέχει επανευρετήριο στο container: $CONTAINER"
docker exec -it "$CONTAINER" python3 /app/index_docs.py
echo "✅ Reindex ολοκληρώθηκε!"
