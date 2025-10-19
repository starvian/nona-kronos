#!/bin/bash
# Convenience script for hybrid (CPU + GPU) deployment
# Usage: ./deploy-hybrid.sh [--with-lb|--stop|--logs|--restart|--status]

set -e

COMPOSE_FILE="docker-compose.hybrid.yml"
CPU_SERVICE="kronos-api-cpu"
GPU_SERVICE="kronos-api-gpu"
LB_SERVICE="nginx-lb"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

USE_LB=false

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

print_section() {
    echo -e "${BLUE}==== $1 ====${NC}"
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

    if ! command -v nvidia-smi &> /dev/null; then
        print_error "nvidia-smi not found. NVIDIA drivers may not be installed."
        return 1
    fi

    if ! nvidia-smi &> /dev/null; then
        print_error "nvidia-smi failed. GPU may not be available."
        return 1
    fi

    print_info "GPU detected"

    if ! docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        print_error "NVIDIA Docker runtime not available."
        return 1
    fi

    print_info "NVIDIA Docker runtime is available"
    return 0
}

# Function to deploy services
deploy() {
    print_section "Deploying Hybrid Configuration"
    print_info "CPU + GPU instances will be started"

    if [ "$USE_LB" = true ]; then
        print_info "Load balancer will be included"
    else
        print_info "Load balancer will NOT be started (use --with-lb to include)"
    fi

    # Check GPU
    if ! check_gpu; then
        print_error "GPU check failed. Cannot deploy GPU service."
        exit 1
    fi

    # Check if services are already running
    if docker ps | grep -q "$CPU_SERVICE\|$GPU_SERVICE"; then
        print_warn "One or more services are already running. Use --restart to restart."
        docker ps | grep "kronos-api"
        exit 0
    fi

    # Start services
    if [ "$USE_LB" = true ]; then
        docker-compose -f "$COMPOSE_FILE" --profile loadbalancer up -d
    else
        docker-compose -f "$COMPOSE_FILE" up -d
    fi

    print_info "Waiting for services to be healthy..."
    sleep 5

    # Wait for health checks
    print_section "Health Checks"

    # Check CPU service
    print_info "Checking CPU service..."
    RETRIES=12
    for i in $(seq 1 $RETRIES); do
        if docker ps | grep -q "$CPU_SERVICE.*healthy"; then
            print_info "CPU service is healthy!"
            break
        fi
        if [ $i -eq $RETRIES ]; then
            print_warn "CPU service health check timeout"
        fi
        sleep 5
    done

    # Check GPU service
    print_info "Checking GPU service..."
    RETRIES=18
    for i in $(seq 1 $RETRIES); do
        if docker ps | grep -q "$GPU_SERVICE.*healthy"; then
            print_info "GPU service is healthy!"
            break
        fi
        if [ $i -eq $RETRIES ]; then
            print_warn "GPU service health check timeout"
        fi
        sleep 5
    done

    # Check load balancer if enabled
    if [ "$USE_LB" = true ]; then
        print_info "Checking load balancer..."
        RETRIES=6
        for i in $(seq 1 $RETRIES); do
            if docker ps | grep -q "$LB_SERVICE.*healthy"; then
                print_info "Load balancer is healthy!"
                break
            fi
            if [ $i -eq $RETRIES ]; then
                print_warn "Load balancer health check timeout"
            fi
            sleep 5
        done
    fi

    # Show running services
    print_section "Running Services"
    docker ps | grep "kronos\|nginx-lb" || docker ps

    # Show access information
    print_section "Access Information"
    if [ "$USE_LB" = true ]; then
        print_info "Load Balancer: http://localhost:8080"
        print_info "  - Single predictions: http://localhost:8080/v1/predict/single (routed to CPU)"
        print_info "  - Batch predictions: http://localhost:8080/v1/predict/batch (routed to GPU)"
        print_info "  - Force CPU: Add header 'X-Kronos-Device: cpu'"
        print_info "  - Force GPU: Add header 'X-Kronos-Device: gpu'"
    else
        print_info "CPU Service: http://$CPU_SERVICE:8000 (internal only)"
        print_info "GPU Service: http://$GPU_SERVICE:8000 (internal only)"
    fi

    print_info ""
    print_info "Useful commands:"
    print_info "  - View logs: ./deploy-hybrid.sh --logs"
    print_info "  - Check status: ./deploy-hybrid.sh --status"
    print_info "  - Stop services: ./deploy-hybrid.sh --stop"
}

# Function to stop services
stop() {
    print_info "Stopping hybrid deployment..."
    if [ "$USE_LB" = true ]; then
        docker-compose -f "$COMPOSE_FILE" --profile loadbalancer down
    else
        docker-compose -f "$COMPOSE_FILE" down
    fi
    print_info "All services stopped"
}

# Function to show logs
logs() {
    print_info "Showing logs for all services..."
    print_info "Press Ctrl+C to exit"
    echo ""

    if [ "$USE_LB" = true ]; then
        docker-compose -f "$COMPOSE_FILE" --profile loadbalancer logs -f
    else
        docker-compose -f "$COMPOSE_FILE" logs -f
    fi
}

# Function to restart services
restart() {
    print_info "Restarting hybrid deployment..."
    stop
    sleep 2
    deploy
}

# Function to show status
status() {
    print_section "Hybrid Deployment Status"

    # Check CPU service
    if docker ps | grep -q "$CPU_SERVICE"; then
        print_info "CPU Service: RUNNING"
        if docker inspect "$CPU_SERVICE" | grep -q '"Status": "healthy"'; then
            print_info "  Health: HEALTHY"
        else
            print_warn "  Health: UNHEALTHY or STARTING"
        fi
    else
        print_warn "CPU Service: NOT RUNNING"
    fi

    # Check GPU service
    if docker ps | grep -q "$GPU_SERVICE"; then
        print_info "GPU Service: RUNNING"
        if docker inspect "$GPU_SERVICE" | grep -q '"Status": "healthy"'; then
            print_info "  Health: HEALTHY"
        else
            print_warn "  Health: UNHEALTHY or STARTING"
        fi

        # Check GPU access
        if docker exec "$GPU_SERVICE" nvidia-smi &> /dev/null; then
            print_info "  GPU: ACCESSIBLE"
        else
            print_warn "  GPU: NOT ACCESSIBLE"
        fi
    else
        print_warn "GPU Service: NOT RUNNING"
    fi

    # Check load balancer
    if docker ps | grep -q "$LB_SERVICE"; then
        print_info "Load Balancer: RUNNING"
        if docker inspect "$LB_SERVICE" | grep -q '"Status": "healthy"'; then
            print_info "  Health: HEALTHY"
        else
            print_warn "  Health: UNHEALTHY or STARTING"
        fi
    else
        print_info "Load Balancer: NOT RUNNING (use --with-lb to start)"
    fi

    # Show containers
    print_section "Container Details"
    docker ps | grep "kronos\|nginx" || print_warn "No services running"

    # Resource usage
    if docker ps | grep -q "kronos"; then
        print_section "Resource Usage"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep "kronos\|nginx\|NAME"
    fi
}

# Function to test routing (if load balancer is running)
test_routing() {
    if ! docker ps | grep -q "$LB_SERVICE"; then
        print_error "Load balancer is not running. Start with --with-lb first."
        exit 1
    fi

    print_section "Testing Load Balancer Routing"

    LB_URL="http://localhost:8080"

    # Test single prediction (should go to CPU)
    print_info "Testing single prediction (should route to CPU)..."
    RESPONSE=$(curl -s -X POST "$LB_URL/v1/predict/single" \
        -H "Content-Type: application/json" \
        -H "X-Request-ID: test-single-$(date +%s)" \
        -d '{"data": [[100, 105, 98, 102]], "pred_len": 5}' \
        -w "\n%{http_code}" | tail -n 1)

    if [ "$RESPONSE" = "200" ]; then
        print_info "Single prediction: SUCCESS (routed to CPU)"
    else
        print_warn "Single prediction: HTTP $RESPONSE"
    fi

    sleep 1

    # Test batch prediction (should go to GPU)
    print_info "Testing batch prediction (should route to GPU)..."
    RESPONSE=$(curl -s -X POST "$LB_URL/v1/predict/batch" \
        -H "Content-Type: application/json" \
        -H "X-Request-ID: test-batch-$(date +%s)" \
        -d '{"batch": [{"data": [[100, 105, 98, 102]], "pred_len": 5}]}' \
        -w "\n%{http_code}" | tail -n 1)

    if [ "$RESPONSE" = "200" ]; then
        print_info "Batch prediction: SUCCESS (routed to GPU)"
    else
        print_warn "Batch prediction: HTTP $RESPONSE"
    fi

    sleep 1

    # Test forced CPU routing
    print_info "Testing forced CPU routing (batch to CPU)..."
    RESPONSE=$(curl -s -X POST "$LB_URL/v1/predict/batch" \
        -H "Content-Type: application/json" \
        -H "X-Kronos-Device: cpu" \
        -H "X-Request-ID: test-force-cpu-$(date +%s)" \
        -d '{"batch": [{"data": [[100, 105, 98, 102]], "pred_len": 5}]}' \
        -w "\n%{http_code}" | tail -n 1)

    if [ "$RESPONSE" = "200" ]; then
        print_info "Forced CPU: SUCCESS"
    else
        print_warn "Forced CPU: HTTP $RESPONSE"
    fi

    print_section "Routing Test Complete"
    print_info "Check NGINX logs for routing details:"
    print_info "  docker-compose -f $COMPOSE_FILE logs nginx-lb"
}

# Main script
main() {
    check_docker

    # Check for --with-lb flag in any position
    for arg in "$@"; do
        if [ "$arg" = "--with-lb" ]; then
            USE_LB=true
        fi
    done

    # Get primary command (first non-flag argument)
    CMD="${1:-}"
    if [ "$CMD" = "--with-lb" ] && [ -n "${2:-}" ]; then
        CMD="${2:-}"
    fi

    case "$CMD" in
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
        --test)
            test_routing
            ;;
        --help)
            echo "Usage: $0 [--with-lb] [OPTION]"
            echo ""
            echo "Deploy Kronos FastAPI Service in hybrid mode (CPU + GPU)"
            echo ""
            echo "Options:"
            echo "  (no option)  Deploy services"
            echo "  --with-lb    Include NGINX load balancer"
            echo "  --stop       Stop all services"
            echo "  --logs       Show logs (follow mode)"
            echo "  --restart    Restart all services"
            echo "  --status     Show detailed status"
            echo "  --test       Test load balancer routing (requires --with-lb)"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                Deploy CPU + GPU without load balancer"
            echo "  $0 --with-lb      Deploy CPU + GPU with load balancer"
            echo "  $0 --with-lb --stop   Stop all services including load balancer"
            ;;
        ""|"--with-lb")
            deploy
            ;;
        *)
            print_error "Unknown option: $CMD"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
