#!/bin/bash
set -e

echo "---------------------------------------"
echo " SAFE DOCKER CLEANUP SCRIPT "
echo "---------------------------------------"

echo "Step 1: Detecting images currently in use..."
USED_IMAGES=$(docker ps --format "{{.Image}}" | sort | uniq)
echo "Images in use:"
echo "$USED_IMAGES"
echo ""

echo "Step 2: Removing dangling images (<none>)..."
docker image prune -f
echo ""

echo "Step 3: Removing unused images..."
ALL_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | uniq)

for IMG in $ALL_IMAGES; do
    if echo "$USED_IMAGES" | grep -q "$IMG"; then
        echo "Keeping: $IMG (in use)"
    elif [[ "$IMG" == "nginx:latest" ]]; then
        echo "Keeping nginx"
    elif [[ "$IMG" == "<none>:<none>" ]]; then
        echo "Skipping dangling placeholder"
    else
        echo "Removing unused image: $IMG"
        docker rmi -f "$IMG" || true
    fi
done
echo ""

echo "Step 4: Cleaning unused volumes..."
docker volume prune -f
echo ""

echo "Step 5: Cleaning build cache..."
docker builder prune -a -f
echo ""

echo "✅ Cleanup completed."
echo "---------------------------------------"

echo "Disk usage after cleanup:"
docker system df
