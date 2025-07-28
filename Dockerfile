# Use the official Playwright Python image with all dependencies preinstalled
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# Set the working directory inside the container
WORKDIR /app

# Copy all project files into the container
COPY . /app

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright browsers (Chromium, Firefox, WebKit)
RUN playwright install

# Run the Flask app (make sure your app reads the port from os.environ["PORT"])
CMD ["python", "src/app.py"]