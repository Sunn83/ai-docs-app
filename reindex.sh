#!/bin/bash
docker exec -it ai-docs-app_backend_1 python3 /app/index_docs.py
echo "✅ Reindex command executed"
