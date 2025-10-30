#!/bin/bash
# Start Data API service

set -e

echo "========================================="
echo "Starting Kronos Data API Service"
echo "========================================="

# Check if network exists
if ! docker network inspect kronos-network &>/dev/null; then
    echo "Creating kronos-network..."
    docker network create kronos-network
    echo "✓ Network created"
fi

# Build and start service
echo ""
echo "Building and starting service..."
docker-compose up -d --build

# Wait for service to be ready
echo ""
echo "Waiting for service to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8001/v1/healthz > /dev/null 2>&1; then
        echo ""
        echo "========================================="
        echo "✓ Data API service is ready!"
        echo "========================================="
        echo ""
        echo "Service Information:"
        echo "  - API URL:     http://localhost:8001"
        echo "  - API Docs:    http://localhost:8001/docs"
        echo "  - Redoc:       http://localhost:8001/redoc"
        echo "  - Health:      http://localhost:8001/v1/healthz"
        echo ""
        echo "ClickHouse Connection:"
        echo "  - Host:        192.168.1.110:19999"
        echo "  - Database:    default"
        echo ""
        echo "View logs:"
        echo "  docker-compose logs -f"
        echo ""
        exit 0
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "Waiting... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done

echo ""
echo "✗ Service failed to start within timeout"
echo "Check logs with: docker-compose logs"
exit 1
