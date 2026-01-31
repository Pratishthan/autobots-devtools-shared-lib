# ABOUTME: Multi-stage Dockerfile for bro-chat production deployment.
# ABOUTME: Uses uv for fast dependency management and minimal image size.

# Stage 1: Build dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment (production only)
RUN uv sync --frozen --no-cache --no-dev

# Stage 2: Runtime
FROM python:3.12-slim-bookworm

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Expose the application port
EXPOSE 1337

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:1337/health || exit 1

# Run the Chainlit application
CMD ["uv", "run", "chainlit", "run", "src/bro_chat/app.py", "--host", "0.0.0.0", "--port", "1337"]
