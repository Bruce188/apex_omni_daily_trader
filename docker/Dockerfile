FROM python:3.12-slim

LABEL maintainer="ApexOmni Trading Bot"
LABEL description="24/7 Continuous Trading Bot for ApexOmni"

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot/ ./bot/
COPY data/ ./data/
COPY analytics/ ./analytics/
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create data directory
RUN mkdir -p /app/data /app/logs

# Set environment defaults
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from bot.config import Config; Config.load()" || exit 1

# Run continuous daemon
ENTRYPOINT ["python", "scripts/run_continuous.py"]
CMD ["--check-interval", "300"]
