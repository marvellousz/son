# Use official astral-sh uv image for superfast builds
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Compile bytecode for optimal startup speed
ENV UV_COMPILE_BYTECODE=1

# Copy dependency lists and project config
COPY pyproject.toml uv.lock README.md ./

# Sync dependencies without installing the project itself
RUN uv sync --frozen --no-install-project --no-dev

# Final slim stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy migration configuration, models and application code
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY main.py ./main.py

# Create persistent storage directories
RUN mkdir -p data knowledge/personal knowledge/work knowledge/docs

# Expose API port (FastAPI)
EXPOSE 8000

# Execute entrypoint script
CMD ["python", "main.py"]
