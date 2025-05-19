FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    swig \
    libssl-dev \
    libffi-dev \
    libswisseph-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install gunicorn==22.0.0 -r requirements.txt --no-cache-dir
RUN gunicorn --version
COPY . .
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "2", "--threads", "2"]
