# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies with minimal packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for some ML packages)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with retry
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt || \
    (echo "Retrying with increased timeout..." && \
     pip install --no-cache-dir --default-timeout=1000 -r requirements.txt)

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p downloads outputs refs cloned_audio models storage

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TRANSFORMERS_OFFLINE=0
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import telegram" || exit 1

# Run the bot
CMD ["python", "-m", "bot.handlers"]
