FROM python:3.12-slim

LABEL maintainer="ApexOmni Trading Bot"
LABEL description="Daily Trading Bot for ApexOmni Staking Optimization"

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -r -s /bin/false -m appuser

# Copy application code
COPY bot/ ./bot/
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create data directory with correct ownership
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment defaults
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from bot.config import Config; Config.load()" || exit 1

# Default entry point for one-shot trading (GH Actions overrides this)
ENTRYPOINT ["python", "scripts/run_bot.py"]
CMD ["--live"]
