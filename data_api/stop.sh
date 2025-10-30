#!/bin/bash
# Stop Data API service

set -e

echo "========================================="
echo "Stopping Kronos Data API Service"
echo "========================================="

docker-compose down

echo ""
echo "✓ Service stopped"
echo ""
echo "To view logs before stopping:"
echo "  docker-compose logs"
echo ""
echo "To completely remove (including volumes):"
echo "  docker-compose down -v"
echo ""
