#!/bin/bash
# Development startup script with Doppler integration

set -e

echo "🚀 Starting NLLB Translation System (Development)"
echo "================================================"

# Check if Doppler is configured
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI is not installed. Please install it first:"
    echo "   curl -Ls --tlsv1.2 --proto '=https' --retry 3 https://cli.doppler.com/install.sh | sudo sh"
    exit 1
fi

echo "🔐 Using Doppler for secrets management"
echo "📡 Starting development containers..."

# Start development environment with Doppler secrets
doppler run -- docker compose up --build

echo "✅ Development environment stopped"
