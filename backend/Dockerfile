# Backend Dockerfile for NLLB Translation API
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies and system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    libsqlite3-dev \
    wget \
    libbz2-dev \
    curl \
    git \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Download and compile Python 3.12
RUN cd /tmp \
    && wget https://www.python.org/ftp/python/3.12.6/Python-3.12.6.tgz \
    && tar xzf Python-3.12.6.tgz \
    && cd Python-3.12.6 \
    && ./configure --enable-optimizations --with-ensurepip=install \
    && make -j$(nproc) \
    && make altinstall \
    && cd / \
    && rm -rf /tmp/Python-3.12.6*

# Create symlinks for easier access
RUN ln -s /usr/local/bin/python3.12 /usr/local/bin/python \
    && ln -s /usr/local/bin/pip3.12 /usr/local/bin/pip

# Install uv package manager
RUN python -m pip install uv

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy uv configuration files and README
COPY pyproject.toml uv.lock README.md ./

# Create virtual environment and install dependencies
RUN python -m uv venv /opt/venv --python python
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
