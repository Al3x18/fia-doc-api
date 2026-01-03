# Use the official Playwright Python image with all dependencies preinstalled
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Set the working directory inside the container
WORKDIR /app

# Add src to PYTHONPATH
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Copy all project files into the container
COPY . /app

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright browsers (Chromium, Firefox, WebKit)
RUN playwright install

# Run the Flask app with Gunicorn (production WSGI server)
# Railway will set the PORT environment variable dynamically
# Use 0.0.0.0 to bind to all interfaces and read PORT from environment
CMD gunicorn -w 4 -b 0.0.0.0:${PORT:-8080} --timeout 120 --access-logfile - --error-logfile - src.app:app