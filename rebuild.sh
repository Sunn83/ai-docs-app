#!/bin/bash
docker compose down --volumes --remove-orphans
docker compose up -d --build
./reindex.sh
