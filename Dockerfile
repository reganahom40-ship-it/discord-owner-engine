FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    DATABASE_PATH=/data/platform.db \
    ENABLE_BACKGROUND_WORKER=true

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8080", "--timeout", "120", "wsgi:app"]
