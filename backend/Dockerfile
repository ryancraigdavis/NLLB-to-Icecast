# Backend Dockerfile for NLLB Translation API
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3-pip \
    curl \
    git \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy uv configuration files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN uv sync --frozen

# Create models directory with proper permissions
RUN mkdir -p /app/models && chown -R appuser:appuser /app/models

# Copy source code
COPY --chown=appuser:appuser src/ ./src/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set environment variables for production
ENV NLLB_HOST=0.0.0.0
ENV NLLB_PORT=8000
ENV NLLB_ENVIRONMENT=production
ENV NLLB_MODEL_CACHE_DIR=/app/models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["/opt/venv/bin/python", "-m", "nllb_to_icecast.run_production"]
