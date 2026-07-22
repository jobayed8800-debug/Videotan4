FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including audio/video libraries
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libavdevice-dev \
    libavfilter-dev \
    libsndfile1-dev \
    portaudio19-dev \
    python3-dev \
    build-essential \
    pkg-config \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for some packages)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Install audio/video dependencies first
RUN pip install --no-cache-dir av==10.0.0

# Copy requirements
COPY requirements.txt .

# Install requirements in batches
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p downloads outputs refs cloned_audio models storage

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PIP_NO_CACHE_DIR=1

EXPOSE 8080

CMD ["python", "-m", "bot.handlers"]ENV TRANSFORMERS_OFFLINE=0
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import telegram" || exit 1

# Run the bot
CMD ["python", "-m", "bot.handlers"]
