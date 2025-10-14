#!/bin/bash

# Kronos FastAPI Docker Build Script
# Builds Docker image with proper context and tagging

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="kronos-fastapi"
DEFAULT_TAG="latest"
BUILD_CONTEXT="../../"  # gitSource directory
DOCKERFILE="./Dockerfile"

# Parse arguments
TAG="${1:-$DEFAULT_TAG}"
PUSH="${2:-false}"

echo -e "${BLUE}🐳 Kronos FastAPI Docker Build${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Verify we're in the right directory
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ Error: Dockerfile not found at $DOCKERFILE${NC}"
    echo -e "${YELLOW}   Please run this script from services/kronos_fastapi/ directory${NC}"
    exit 1
fi

# Verify build context exists
if [ ! -d "$BUILD_CONTEXT" ]; then
    echo -e "${RED}❌ Error: Build context directory not found at $BUILD_CONTEXT${NC}"
    exit 1
fi

# Display build info
echo -e "${GREEN}📦 Build Configuration:${NC}"
echo -e "   Image name: ${BLUE}$IMAGE_NAME${NC}"
echo -e "   Tag:        ${BLUE}$TAG${NC}"
echo -e "   Context:    ${BLUE}$(cd $BUILD_CONTEXT && pwd)${NC}"
echo -e "   Dockerfile: ${BLUE}$DOCKERFILE${NC}"
echo ""

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi

# Build image
echo -e "${GREEN}🔨 Building Docker image...${NC}"
echo ""

docker build \
    --file "$DOCKERFILE" \
    --tag "$IMAGE_NAME:$TAG" \
    --tag "$IMAGE_NAME:latest" \
    "$BUILD_CONTEXT"

BUILD_EXIT_CODE=$?

if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Build successful!${NC}"
    echo ""

    # Show image info
    echo -e "${GREEN}📊 Image Information:${NC}"
    docker images "$IMAGE_NAME:$TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    echo ""

    # Security scan (if trivy is installed)
    if command -v trivy &> /dev/null; then
        echo -e "${YELLOW}🔍 Running security scan...${NC}"
        trivy image --severity HIGH,CRITICAL "$IMAGE_NAME:$TAG" || true
        echo ""
    fi

    # Push if requested
    if [ "$PUSH" = "true" ]; then
        echo -e "${YELLOW}📤 Pushing image to registry...${NC}"
        docker push "$IMAGE_NAME:$TAG"
        echo -e "${GREEN}✅ Push successful!${NC}"
    fi

    echo -e "${GREEN}🎉 All done!${NC}"
    echo ""
    echo -e "${BLUE}To run the container:${NC}"
    echo -e "   ${YELLOW}docker-compose up -d${NC}"
    echo ""
    echo -e "${BLUE}Or manually:${NC}"
    echo -e "   ${YELLOW}docker run -p 8000:8000 \\"
    echo -e "     -v /data/ws/kronos/models:/models:ro \\"
    echo -e "     $IMAGE_NAME:$TAG${NC}"
    echo ""

else
    echo ""
    echo -e "${RED}❌ Build failed with exit code $BUILD_EXIT_CODE${NC}"
    exit $BUILD_EXIT_CODE
fi
