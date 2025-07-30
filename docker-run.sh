#!/bin/bash
# Docker run script for boat-counter on Raspberry Pi

# Set the image name and tag
IMAGE_NAME="boat-counter"
TAG="latest"

# Make sure snapshots and logs directories exist
mkdir -p ./logs ./snapshots

# Parse command line arguments
REBUILD=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --rebuild) REBUILD=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Check if we need to build the image
if [[ "$(docker images -q $IMAGE_NAME:$TAG 2> /dev/null)" == "" ]] || [[ "$REBUILD" == true ]]; then
  echo "🔨 Building Docker image..."
  docker build --no-cache -t $IMAGE_NAME:$TAG .
fi

# Run the container with access to camera and X11 display
docker run --rm \
  --name boat-counter-app \
  --privileged \
  --device=/dev/video0:/dev/video0 \
  -v /opt/vc:/opt/vc \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/snapshots:/app/snapshots \
  -v $(pwd)/gsheets_creds.json:/app/gsheets_creds.json:ro \
  -v $(pwd)/mask.png:/app/mask.png:ro \
  -e DISPLAY=$DISPLAY \
  -e PYTHONUNBUFFERED=1 \
  $IMAGE_NAME:$TAG python A2_boat_counter_test_full_cooldown.py

echo "Container stopped. Check logs in ./logs directory." 