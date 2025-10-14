#!/bin/bash

# Start Kronos FastAPI Service
# This script starts the uvicorn server from the correct directory

cd "$(dirname "$0")/../.." || exit 1

PORT=${1:-8000}
HOST=${2:-0.0.0.0}
WORKERS=${3:-1}

echo "🚀 Starting Kronos FastAPI Service..."
echo "📍 Working directory: $(pwd)"
echo "🌐 Host: $HOST"
echo "🔌 Port: $PORT"
echo "👷 Workers: $WORKERS"
echo ""

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "❌ Error: Port $PORT is already in use!"
    echo "   Use './stop.sh $PORT' to stop the existing service"
    exit 1
fi

# Start the service
if [ "$WORKERS" -eq 1 ]; then
    # Single worker with reload for development
    echo "🔧 Starting in development mode (with auto-reload)..."
    uvicorn services.kronos_fastapi.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload
else
    # Multiple workers for production
    echo "🏭 Starting in production mode ($WORKERS workers)..."
    uvicorn services.kronos_fastapi.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS"
fi
