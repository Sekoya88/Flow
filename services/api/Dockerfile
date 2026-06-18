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

# Entrypoints generated here so line endings are guaranteed LF (avoids Windows CRLF
# corrupting the shebang). exec 2>&1 merges stderr into stdout so Railway captures
# uvicorn/arq startup errors and tracebacks (Railway only forwards stdout).
RUN printf '#!/bin/sh\nexec 2>&1\nexec /app/.venv/bin/uvicorn flow.interfaces.http.main:app --host 0.0.0.0 --port "${PORT:-8000}"\n' > /app/start-api.sh \
 && printf '#!/bin/sh\nexec 2>&1\nexec /app/.venv/bin/arq flow.infrastructure.queue.worker.WorkerSettings\n' > /app/start-worker.sh \
 && chmod +x /app/start-api.sh /app/start-worker.sh

CMD ["/app/start-api.sh"]
