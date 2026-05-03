#!/bin/bash
# Blindspot — One-Command Demo Launch

set -e

echo "🚀 Starting Blindspot Demo..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Set demo mode
export DEMO_MODE=true

# Start services
docker-compose up --build

echo "✅ Blindspot is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
