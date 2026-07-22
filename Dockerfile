FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    espeak-ng \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Create directories
RUN mkdir -p downloads outputs refs cloned_audio models

# Expose port
EXPOSE 8080

# Run bot
CMD ["python", "-m", "bot.handlers"]
