FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md uv.lock ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY flow ./flow
RUN uv sync --frozen --no-dev
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "uv run uvicorn flow.interfaces.http.main:app --host 0.0.0.0 --port ${PORT}"]
