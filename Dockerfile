# Stage 1: build the web console (React + Vite) into static files
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: Python API, which also serves the console at /
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sentinelai sentinelai
COPY policies policies
COPY benchmark/results.json benchmark/results.json
COPY --from=web /web/dist web/dist
RUN useradd -m sentinel && mkdir -p /app/var && chown -R sentinel /app
USER sentinel
ENV SENTINEL_DB_PATH=/app/var/sentinel.db SENTINEL_MODEL_DIR=/app/var/models PYTHONUNBUFFERED=1
EXPOSE 8000
# Train on first start if no model is present, then serve the API and console
CMD ["sh", "-c", "[ -f /app/var/models/current.json ] || python -m sentinelai train; exec python -m sentinelai serve --port ${PORT:-8000}"]
