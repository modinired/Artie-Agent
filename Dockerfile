# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev tesseract-ocr git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install requirements first for better caching
COPY requirements.prod.txt /app/requirements.prod.txt
RUN pip install --no-cache-dir -r /app/requirements.prod.txt

# Copy app
COPY terry /app/terry
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

ENV UVICORN_WORKERS=2
CMD ["python","-m","terry.app.main"]
