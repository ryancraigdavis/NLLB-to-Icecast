# Piper TTS Service - Python 3.12 compatible
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    libgomp1 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Download and install Piper binary
RUN wget -q https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz && \
    tar -xzf piper_linux_x86_64.tar.gz && \
    rm piper_linux_x86_64.tar.gz && \
    chmod +x piper && \
    mv piper /usr/local/bin/ && \
    mv *.so* /usr/local/lib/ && \
    mv espeak-ng* /usr/local/bin/ && \
    ldconfig

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    requests \
    pydantic \
    python-multipart

# Create directories
RUN mkdir -p /app/models /app/output

# Copy application files
COPY tts_api.py /app/
COPY download_models.py /app/

# Download voice models at build time
RUN python /app/download_models.py

# Expose port
EXPOSE 8001

# Run the TTS API service
CMD ["uvicorn", "tts_api:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]