# LAWA Backend Dockerfile
# Python 3.12 + FastAPI + PostgreSQL + Redis
FROM python:3.12-slim AS backend

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY src/ ./src/
COPY .env.example .env

EXPOSE 6288

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:6288/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "6288"]
