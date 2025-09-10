# Doppler Setup Guide

This guide explains how to configure Doppler for managing secrets in the NLLB Translation System.

## Prerequisites

1. **Doppler CLI installed**:
   ```bash
   curl -Ls --tlsv1.2 --proto '=https' --retry 3 https://cli.doppler.com/install.sh | sudo sh
   ```

2. **Doppler account** with a configured project

## Environment Variables

Configure these environment variables in your Doppler project:

### Backend Configuration (Required)

| Variable | Description | Example |
|----------|-------------|---------|
| `NLLB_HOST` | Backend host | `0.0.0.0` |
| `NLLB_PORT` | Backend port | `8000` |
| `NLLB_ENVIRONMENT` | Environment name | `production` |
| `NLLB_LOG_LEVEL` | Logging level | `INFO` |
| `NLLB_CORS_ORIGINS` | Allowed CORS origins | `["https://yourdomain.com"]` |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NLLB_API_KEY` | API authentication key | None |
| `NLLB_MODEL_CACHE_DIR` | Model storage directory | `/app/models` |
| `NLLB_TORCH_DEVICE` | PyTorch device | `auto` |
| `NLLB_MAX_CONNECTIONS` | Max WebSocket connections | `100` |
| `NLLB_CONNECTION_TIMEOUT` | Connection timeout (seconds) | `30` |

### Frontend Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `PUBLIC_API_URL` | Backend API URL | `https://api.yourdomain.com` |

## Setup Instructions

### 1. Configure Doppler Project

```bash
# Login to Doppler
doppler login

# Navigate to your project directory
cd /path/to/NLLB-to-Icecast

# Setup Doppler for this project
doppler setup
```

### 2. Configure Environments

Create separate environments for development and production:

- **Development**: `dev` or `development`
- **Production**: `prd` or `production`

### 3. Add Environment Variables

#### Via Doppler Dashboard
1. Go to your Doppler dashboard
2. Select your project and environment
3. Add the required environment variables listed above

#### Via Doppler CLI
```bash
# Set environment variables
doppler secrets set NLLB_HOST=0.0.0.0
doppler secrets set NLLB_PORT=8000
doppler secrets set NLLB_ENVIRONMENT=production
doppler secrets set NLLB_LOG_LEVEL=INFO

# For production, set specific CORS origins
doppler secrets set NLLB_CORS_ORIGINS='["https://yourdomain.com"]'
```

## Running the Application

### Development
```bash
# Make sure you're in the development environment
doppler setup

# Start development environment
./scripts/run-dev.sh
```

### Production
```bash
# Switch to production environment
doppler setup  # Select production environment

# Start production environment
./scripts/run-prod.sh
```

## Docker Integration

The Docker containers automatically receive environment variables from Doppler through the startup scripts. No additional configuration is needed in the Docker files.

## Security Notes

1. **Never commit secrets** to version control
2. **Use different Doppler environments** for dev/staging/production
3. **Rotate secrets regularly** through the Doppler dashboard
4. **Use Doppler service tokens** for CI/CD pipelines
5. **Enable Doppler audit logs** to track secret access

## Troubleshooting

### Check Doppler Configuration
```bash
# Verify current configuration
doppler configure

# List available projects
doppler projects

# View current secrets (without values)
doppler secrets
```

### Test Secret Access
```bash
# Test that Doppler can inject secrets
doppler run -- env | grep NLLB_
```

### Common Issues

1. **"Doppler is not configured"**
   - Run `doppler setup` and select your project/environment

2. **"Permission denied"**
   - Check your Doppler project permissions
   - Ensure you're logged in: `doppler login`

3. **"Environment variables not loading"**
   - Verify environment variable names (case-sensitive)
   - Check that you're in the correct Doppler environment

## Example Doppler Configuration

For a typical production setup:

```bash
# Core settings
NLLB_HOST=0.0.0.0
NLLB_PORT=8000
NLLB_ENVIRONMENT=production
NLLB_LOG_LEVEL=INFO
NLLB_DEBUG=false

# Security
NLLB_CORS_ORIGINS=["https://yourdomain.com"]
NLLB_API_KEY=your-secret-api-key

# Performance
NLLB_MAX_CONNECTIONS=100
NLLB_CONNECTION_TIMEOUT=30

# Frontend
PUBLIC_API_URL=https://api.yourdomain.com
```