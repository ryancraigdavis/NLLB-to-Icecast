# Docker Setup Guide

This guide explains how to run the NLLB Translation System using Docker and Docker Compose.

## Prerequisites

1. **Docker** (with NVIDIA GPU support for ML models)
2. **Docker Compose V2**
3. **Doppler CLI** (for secrets management)
4. **NVIDIA GPU** (recommended for faster inference)

## Quick Start

### Development Environment

```bash
# 1. Configure Doppler (first time only)
doppler setup

# 2. Start development environment
./scripts/run-dev.sh
```

### Production Environment

```bash
# 1. Configure Doppler for production
doppler setup  # Select production environment

# 2. Start production environment
./scripts/run-prod.sh
```

## Manual Commands

### Development
```bash
# Start development containers
docker compose up --build

# Run in background
docker compose up --build -d

# View logs
docker compose logs -f

# Stop containers
docker compose down
```

### Production
```bash
# Start production containers
docker compose -f docker-compose.prod.yml up --build -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop containers
docker compose -f docker-compose.prod.yml down
```

## Services

### Development Environment (`docker-compose.yml`)
- **Backend**: FastAPI server on port 8000
- **Frontend**: SvelteKit dev server on port 3000
- **Network**: Internal communication between services
- **Volumes**: Source code mounted for hot reload

### Production Environment (`docker-compose.prod.yml`)
- **Backend**: Production FastAPI server
- **Frontend**: Production SvelteKit build
- **Nginx**: Reverse proxy on ports 80/443
- **Network**: Optimized for production traffic
- **Volumes**: Persistent model storage

## Architecture

```
Development:
┌─────────────────┐    ┌──────────────────┐
│  Frontend:3000  │    │  Backend:8000    │
│  (SvelteKit)    │◄──►│  (FastAPI +      │
│                 │    │   WebSocket)     │
└─────────────────┘    └──────────────────┘

Production:
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Nginx:80/443   │    │  Frontend:3000  │    │  Backend:8000    │
│  (Reverse Proxy)│◄──►│  (SvelteKit)    │◄──►│  (FastAPI +      │
│                 │    │                 │    │   WebSocket)     │
└─────────────────┘    └─────────────────┘    └──────────────────┘
```

## Environment Variables

All environment variables are managed through Doppler. See `DOPPLER_SETUP.md` for configuration details.

### Key Variables:
- `NLLB_ENVIRONMENT`: `development` or `production`
- `NLLB_HOST`: Backend host (0.0.0.0 for containers)
- `NLLB_PORT`: Backend port (8000)
- `PUBLIC_API_URL`: Frontend API endpoint

## GPU Support

The backend container includes NVIDIA GPU support for accelerated ML inference:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

**Requirements**:
- NVIDIA Docker runtime installed
- Compatible GPU with CUDA 12.1+ support

## Audio Device Access

Both containers have access to audio devices for real-time capture:

```yaml
devices:
  - /dev/snd
volumes:
  - /dev/snd:/dev/snd
```

## Persistent Storage

### Model Cache
ML models are cached in a Docker volume to avoid re-downloading:

```yaml
volumes:
  - backend-models:/app/models
```

### SSL Certificates (Production)
SSL certificates should be placed in `nginx/ssl/`:

```
nginx/ssl/
├── cert.pem
└── key.pem
```

## Networking

### Development
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws

### Production
- Application: http://localhost (or your domain)
- API: http://localhost/api
- WebSocket: ws://localhost/ws
- Health Check: http://localhost/health

## Health Checks

Both services include health checks:

### Backend
```bash
curl -f http://localhost:8000/health
```

### Frontend
```bash
curl -f http://localhost:3000
```

## Troubleshooting

### Container Build Issues

1. **NVIDIA GPU not found**:
   ```bash
   # Install NVIDIA Container Runtime
   sudo apt-get install nvidia-container-runtime
   sudo systemctl restart docker
   ```

2. **Permission denied on audio devices**:
   ```bash
   # Add user to audio group
   sudo usermod -a -G audio $USER
   # Restart session
   ```

3. **Doppler secrets not loading**:
   ```bash
   # Verify Doppler configuration
   doppler configure
   doppler secrets
   ```

### Performance Issues

1. **Backend memory usage**:
   - Adjust resource limits in production compose file
   - Monitor model loading with `docker stats`

2. **Frontend build slow**:
   - Use multi-stage Docker builds (already implemented)
   - Increase Docker build memory if needed

### Debugging

1. **View container logs**:
   ```bash
   docker compose logs -f [service-name]
   ```

2. **Execute commands in container**:
   ```bash
   docker compose exec backend bash
   docker compose exec frontend sh
   ```

3. **Check resource usage**:
   ```bash
   docker stats
   ```

## Production Deployment

1. **Configure Doppler production environment**
2. **Set up SSL certificates** in `nginx/ssl/`
3. **Update CORS origins** for your domain
4. **Configure DNS** to point to your server
5. **Start production containers**: `./scripts/run-prod.sh`

## Monitoring

Production containers include structured logging:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

Use external tools like ELK stack or similar for log aggregation in production.

## Security

1. **Use HTTPS** in production (configure SSL in nginx)
2. **Restrict CORS origins** to your domain
3. **Use Doppler** for secret management
4. **Regular updates** of base images
5. **Network isolation** with Docker networks