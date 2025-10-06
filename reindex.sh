#!/bin/bash

# Βεβαιωνόμαστε ότι το backend τρέχει
CONTAINER=$(docker ps --filter "name=backend" --format "{{.ID}}")
if [ -z "$CONTAINER" ]; then
  echo "❌ Backend container is not running"
  exit 1
fi

# Εκτελούμε την επαναδεικτοδότηση
docker exec -it $CONTAINER python /app/index_docs.py -c "index_all_documents()"
echo "✅ Reindex command executed"
