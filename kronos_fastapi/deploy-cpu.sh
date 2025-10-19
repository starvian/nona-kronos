#!/bin/bash
# Convenience script for CPU-only deployment
# Usage: ./deploy-cpu.sh [--stop|--logs|--restart]

set -e

COMPOSE_FILE="docker-compose.cpu.yml"
SERVICE_NAME="kronos-api-cpu"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_info "Docker is running"
}

# Function to deploy service
deploy() {
    print_info "Deploying Kronos FastAPI Service (CPU mode)..."

    # Check if service is already running
    if docker ps | grep -q "$SERVICE_NAME"; then
        print_warn "Service is already running. Use --restart to restart."
        exit 0
    fi

    # Start service
    docker-compose -f "$COMPOSE_FILE" up -d

    print_info "Waiting for service to be healthy..."
    sleep 5

    # Wait for health check
    RETRIES=12
    for i in $(seq 1 $RETRIES); do
        if docker ps | grep -q "$SERVICE_NAME.*healthy"; then
            print_info "Service is healthy!"
            docker ps | grep "$SERVICE_NAME"
            print_info "Access service at: http://localhost:8000 (if port is exposed)"
            print_info "Check logs with: ./deploy-cpu.sh --logs"
            return 0
        fi
        print_info "Waiting for health check... ($i/$RETRIES)"
        sleep 5
    done

    print_warn "Service started but health check not confirmed. Check logs:"
    docker-compose -f "$COMPOSE_FILE" logs --tail 50
}

# Function to stop service
stop() {
    print_info "Stopping Kronos FastAPI Service (CPU mode)..."
    docker-compose -f "$COMPOSE_FILE" down
    print_info "Service stopped"
}

# Function to show logs
logs() {
    print_info "Showing logs for $SERVICE_NAME..."
    docker-compose -f "$COMPOSE_FILE" logs -f
}

# Function to restart service
restart() {
    print_info "Restarting Kronos FastAPI Service (CPU mode)..."
    stop
    sleep 2
    deploy
}

# Function to show status
status() {
    print_info "Checking service status..."

    if docker ps | grep -q "$SERVICE_NAME"; then
        print_info "Service is running:"
        docker ps | grep "$SERVICE_NAME"

        # Try health check
        if docker inspect "$SERVICE_NAME" | grep -q '"Status": "healthy"'; then
            print_info "Health status: HEALTHY"
        else
            print_warn "Health status: UNHEALTHY or STARTING"
        fi
    else
        print_warn "Service is not running"
    fi
}

# Main script
main() {
    check_docker

    case "${1:-}" in
        --stop)
            stop
            ;;
        --logs)
            logs
            ;;
        --restart)
            restart
            ;;
        --status)
            status
            ;;
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Deploy Kronos FastAPI Service in CPU mode"
            echo ""
            echo "Options:"
            echo "  (no option)  Deploy service"
            echo "  --stop       Stop service"
            echo "  --logs       Show logs (follow mode)"
            echo "  --restart    Restart service"
            echo "  --status     Show service status"
            echo "  --help       Show this help message"
            ;;
        "")
            deploy
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
