FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (build-essential for compiling native extensions, tesseract-ocr for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to utilize Docker layer caching
COPY backend/requirements.txt ./backend/requirements.txt

# Install dependencies including Pathway
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir pathway

# Copy backend and machine learning directories
COPY backend/ ./backend
COPY ml/ ./ml

# Configure environment variables
ENV PYTHONPATH="/app:/app/backend:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

EXPOSE 8000

# Start FastAPI server, binding to the PORT environment variable if provided (defaults to 8000)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
