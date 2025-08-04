FROM nvcr.io/nvidia/l4t-pytorch:r32.7.1-pth1.9-py3

# Set up environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-opencv \
    libopencv-dev \
    libgtk-3-dev \
    python3-pip \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    python3-tk \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY config/requirements_jetson.txt .
RUN pip3 install --no-cache-dir -r requirements_jetson.txt

# Copy application code and model files
COPY src/A2_boat_counter_test_full_cooldown.py .
COPY src/sort.py .
COPY models/yolov8n.pt .
COPY config/gsheets_creds.json .

# Create directories
RUN mkdir -p snapshots

# Set default environment variables
ENV VIDEO_DEVICE_INDEX=0
ENV DISPLAY_WINDOW=false

# Run the boat counter application
CMD ["python3", "A2_boat_counter_test_full_cooldown.py"] 