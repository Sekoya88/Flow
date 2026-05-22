FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/flow_mcp/
RUN touch /app/flow_mcp/__init__.py

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "flow_mcp.server:app", "--host", "0.0.0.0", "--port", "8001"]
