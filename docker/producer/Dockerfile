FROM python:3.9-slim

# Add labels for better maintenance
LABEL maintainer="Marcus Rodrigues <marcus.v.rodrigues@outlook.com>"
LABEL description="Pump monitoring data producer service"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ .

# Create non-root user
RUN useradd -m -r -s /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${MONITORING_FLASK_PORT}/health || exit 1

# Command to run the application
CMD ["python", "pump_producer.py"]