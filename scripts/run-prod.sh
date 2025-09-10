#!/bin/bash
# Production startup script with Doppler integration

set -e

echo "🚀 Starting NLLB Translation System (Production)"
echo "================================================="

# Check if Doppler is configured
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI is not installed. Please install it first:"
    echo "   curl -Ls --tlsv1.2 --proto '=https' --retry 3 https://cli.doppler.com/install.sh | sudo sh"
    exit 1
fi

# Check if Doppler is configured for production environment
if ! doppler setup --no-interactive --silent 2>/dev/null; then
    echo "⚠️  Doppler is not configured for this project"
    echo "   Run: doppler setup"
    echo "   Then select your project and PRODUCTION environment"
    exit 1
fi

# Verify we're using production environment
CURRENT_ENV=$(doppler config get environment.slug)
if [ "$CURRENT_ENV" != "prd" ] && [ "$CURRENT_ENV" != "production" ]; then
    echo "⚠️  Warning: Current Doppler environment is '$CURRENT_ENV'"
    echo "   Make sure you're using the production environment"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🔐 Using Doppler for secrets management (Environment: $CURRENT_ENV)"
echo "🏭 Starting production containers..."

# Start production environment with Doppler secrets
doppler run -- docker compose -f docker-compose.prod.yml up --build -d

echo "✅ Production environment started"
echo "🌐 Frontend: http://localhost"
echo "🔌 API: http://localhost/api"
echo "📊 Health: http://localhost/health"
echo ""
echo "📋 View logs: docker compose -f docker-compose.prod.yml logs -f"
echo "🛑 Stop: docker compose -f docker-compose.prod.yml down"