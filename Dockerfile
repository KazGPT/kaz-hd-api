# Add Dockerfile to build custom server
# Base image
FROM python:3.11-slim

# Install system dependencies for Swiss Ephemeris
RUN apt-get update && apt-get install -y \
    build-essential \
    swig \
    libssl-dev \
    libffi-dev \
    libswisseph-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first to leverage caching
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Run the app with Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
