#!/bin/bash

# Stop Kronos FastAPI Service
# This script stops the running uvicorn server

PORT=${1:-8000}
SERVICE_NAME="kronos_fastapi"

echo "🛑 Stopping Kronos FastAPI Service on port $PORT..."

# Find process by port and service name
PID=$(lsof -ti:$PORT)

if [ -z "$PID" ]; then
    echo "❌ No service found running on port $PORT"
    exit 1
fi

# Check if it's the Kronos service
PROCESS_CMD=$(ps -p $PID -o cmd=)
if [[ $PROCESS_CMD == *"kronos_fastapi"* ]]; then
    echo "📝 Found Kronos FastAPI process (PID: $PID)"
    echo "   Command: $PROCESS_CMD"

    # Try graceful shutdown first
    echo "🔄 Attempting graceful shutdown..."
    kill -TERM $PID

    # Wait up to 10 seconds for graceful shutdown
    for i in {1..10}; do
        if ! kill -0 $PID 2>/dev/null; then
            echo "✅ Service stopped successfully"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo "⚠️  Graceful shutdown failed, forcing termination..."
    kill -9 $PID

    if ! kill -0 $PID 2>/dev/null; then
        echo "✅ Service forcefully terminated"
        exit 0
    else
        echo "❌ Failed to stop service"
        exit 1
    fi
else
    echo "⚠️  Process found on port $PORT, but it's not Kronos FastAPI:"
    echo "   Command: $PROCESS_CMD"
    echo ""
    read -p "Do you want to stop it anyway? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill -TERM $PID
        echo "✅ Process terminated"
    else
        echo "❌ Operation cancelled"
        exit 1
    fi
fi
