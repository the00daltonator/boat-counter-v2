FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopencv-dev \
    python3-opencv \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements file
COPY requirements_new.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_new.txt

# Create directories for logs and snapshots
RUN mkdir -p /app/logs /app/snapshots

# Copy application code
COPY *.py /app/

# Set default command - run the latest version
CMD ["python", "boat_counter_full_debug-10.py"] 