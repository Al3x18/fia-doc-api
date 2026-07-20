# Keep the container image and the Python package on the same Playwright version.
# This image already contains Chromium and its Linux system dependencies.
FROM mcr.microsoft.com/playwright/python:v1.54.0-noble

WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=1 \
    MALLOC_ARENA_MAX=2

# Copy dependency metadata first so Railway can reuse the dependency layer.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT at runtime. A single worker prevents concurrent Chromium
# processes from exhausting the memory available to a small Hobby instance.
CMD ["sh", "-c", "exec gunicorn --workers ${WEB_CONCURRENCY:-1} --bind 0.0.0.0:${PORT:-8080} --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - src.app:app"]
