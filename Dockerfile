FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sentinelai sentinelai
COPY dashboard dashboard
COPY policies policies
COPY benchmark/results.json benchmark/results.json
COPY .streamlit .streamlit
RUN useradd -m sentinel && mkdir -p /app/var && chown -R sentinel /app
USER sentinel
ENV SENTINEL_DB_PATH=/app/var/sentinel.db SENTINEL_MODEL_DIR=/app/var/models PYTHONUNBUFFERED=1
EXPOSE 8000 8501
# Train on first start if no model is present, then serve the API
CMD ["sh", "-c", "[ -f /app/var/models/current.json ] || python -m sentinelai train; exec python -m sentinelai serve --port ${PORT:-8000}"]
