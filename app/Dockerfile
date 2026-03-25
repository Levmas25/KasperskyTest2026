FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RQ_JOB_TIMEOUT_SECONDS=3600 \
    RQ_RESULT_TTL_SECONDS=86400 \
    RQ_FAILURE_TTL_SECONDS=604800

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]==3.2.12"

COPY . .

RUN mkdir -p /data/uploads /data/results /data/work \
    && chown -R appuser:appuser /app /data \
    && chmod +x /app/docker/start-cleaner.sh /app/docker/start-worker.sh

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
