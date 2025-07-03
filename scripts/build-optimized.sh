#!/bin/bash

# Build Optimization Script for Churns Project
# This script builds optimized Docker images and shows size comparisons

set -e

echo "🚀 Starting optimized Docker build process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Clean up old images
print_status "Cleaning up old images..."
docker image prune -f

# Build production images
print_status "Building optimized production images..."

# Build API (production stage)
print_status "Building API (production)..."
docker build -t churns-api-optimized:latest --target production -f Dockerfile.api .

# Build Frontend (production)
print_status "Building Frontend (production)..."
docker build -t churns-frontend-optimized:latest -f front_end/Dockerfile ./front_end

# Build development images for comparison
print_status "Building development images for comparison..."

# Build API (development stage)
docker build -t churns-api-dev:latest --target development -f Dockerfile.api .

# Build Frontend (development)
docker build -t churns-frontend-dev:latest -f front_end/Dockerfile.dev ./front_end

# Display size comparison
print_status "Image size comparison:"
echo ""
echo "📊 PRODUCTION IMAGES:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "(churns.*optimized|REPOSITORY)"

echo ""
echo "🔧 DEVELOPMENT IMAGES:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "(churns.*dev|REPOSITORY)"

echo ""
echo "📈 OLD IMAGES (for comparison):"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "(churns-(api|frontend).*latest|REPOSITORY)" | grep -v optimized | grep -v dev

# Calculate savings
print_status "Calculating potential savings..."

# Get old and new sizes (this is a simplified calculation)
OLD_API_SIZE=$(docker images --format "{{.Size}}" churns-api:latest 2>/dev/null || echo "0B")
NEW_API_SIZE=$(docker images --format "{{.Size}}" churns-api-optimized:latest 2>/dev/null || echo "0B")

OLD_FRONTEND_SIZE=$(docker images --format "{{.Size}}" churns-frontend:latest 2>/dev/null || echo "0B")
NEW_FRONTEND_SIZE=$(docker images --format "{{.Size}}" churns-frontend-optimized:latest 2>/dev/null || echo "0B")

echo ""
print_success "✅ Optimized images built successfully!"
echo ""
echo "🎯 OPTIMIZATION RESULTS:"
echo "  • API: $OLD_API_SIZE → $NEW_API_SIZE"
echo "  • Frontend: $OLD_FRONTEND_SIZE → $NEW_FRONTEND_SIZE"
echo ""
echo "🔍 KEY OPTIMIZATIONS APPLIED:"
echo "  • Multi-stage builds for smaller production images"
echo "  • Removed unnecessary build tools from production"
echo "  • Optimized layer caching"
echo "  • Excluded data directory from API image"
echo "  • Proper .dockerignore configurations"
echo "  • Production-specific configurations"
echo ""
echo "🚀 NEXT STEPS:"
echo "  • Test with: docker-compose -f docker-compose.yml up"
echo "  • Development: docker-compose -f docker-compose.dev.yml up"
echo "  • Deploy production images to your container registry"
echo ""

print_success "Build optimization complete!" 