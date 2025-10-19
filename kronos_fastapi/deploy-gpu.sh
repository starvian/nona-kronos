#!/bin/bash
# Convenience script for GPU-only deployment
# Usage: ./deploy-gpu.sh [--stop|--logs|--restart|--check-gpu]

set -e

COMPOSE_FILE="docker-compose.gpu.yml"
SERVICE_NAME="kronos-api-gpu"

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

# Function to check GPU availability
check_gpu() {
    print_info "Checking GPU availability..."

    # Check if nvidia-smi is available on host
    if ! command -v nvidia-smi &> /dev/null; then
        print_error "nvidia-smi not found. NVIDIA drivers may not be installed."
        return 1
    fi

    # Check GPU
    if ! nvidia-smi &> /dev/null; then
        print_error "nvidia-smi failed. GPU may not be available."
        return 1
    fi

    print_info "GPU detected:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

    # Check NVIDIA Docker runtime
    if ! docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        print_error "NVIDIA Docker runtime not available."
        print_error "Please install nvidia-docker2: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
        return 1
    fi

    print_info "NVIDIA Docker runtime is available"
    return 0
}

# Function to deploy service
deploy() {
    print_info "Deploying Kronos FastAPI Service (GPU mode)..."

    # Check GPU first
    if ! check_gpu; then
        print_error "GPU check failed. Cannot deploy GPU service."
        exit 1
    fi

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
    RETRIES=18  # Longer for GPU (model loading)
    for i in $(seq 1 $RETRIES); do
        if docker ps | grep -q "$SERVICE_NAME.*healthy"; then
            print_info "Service is healthy!"
            docker ps | grep "$SERVICE_NAME"

            # Verify GPU is accessible from container
            print_info "Verifying GPU access from container..."
            if docker exec "$SERVICE_NAME" nvidia-smi &> /dev/null; then
                print_info "GPU is accessible from container!"
            else
                print_warn "GPU may not be accessible from container. Check logs."
            fi

            print_info "Access service at: http://localhost:8001 (if port is exposed)"
            print_info "Check logs with: ./deploy-gpu.sh --logs"
            print_info "Check GPU usage with: ./deploy-gpu.sh --gpu-status"
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
    print_info "Stopping Kronos FastAPI Service (GPU mode)..."
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
    print_info "Restarting Kronos FastAPI Service (GPU mode)..."
    stop
    sleep 2
    deploy
}

# Function to show GPU status
gpu_status() {
    print_info "GPU Status:"
    if docker ps | grep -q "$SERVICE_NAME"; then
        docker exec "$SERVICE_NAME" nvidia-smi
    else
        print_error "Service is not running. Start it first with: ./deploy-gpu.sh"
        exit 1
    fi
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

        # Check device from readyz endpoint
        print_info "Checking device configuration..."
        if command -v curl &> /dev/null; then
            DEVICE=$(docker exec "$SERVICE_NAME" curl -s http://localhost:8000/v1/readyz 2>/dev/null | grep -o '"device":"[^"]*"' || echo "")
            if [ -n "$DEVICE" ]; then
                print_info "Device: $DEVICE"
            fi
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
        --check-gpu)
            check_gpu
            ;;
        --gpu-status)
            gpu_status
            ;;
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Deploy Kronos FastAPI Service in GPU mode"
            echo ""
            echo "Options:"
            echo "  (no option)     Deploy service"
            echo "  --stop          Stop service"
            echo "  --logs          Show logs (follow mode)"
            echo "  --restart       Restart service"
            echo "  --status        Show service status"
            echo "  --check-gpu     Check GPU availability"
            echo "  --gpu-status    Show GPU status from container"
            echo "  --help          Show this help message"
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
