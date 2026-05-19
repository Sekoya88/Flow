FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml README.md uv.lock ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY flow ./flow
COPY scripts ./scripts
RUN UV_HTTP_TIMEOUT=120 uv sync --frozen --no-dev
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "uv run uvicorn flow.interfaces.http.main:app --host 0.0.0.0 --port ${PORT}"]
