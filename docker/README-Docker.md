# Docker Setup for Boat Counter on Raspberry Pi 4

This guide will help you set up and run the Boat Counter application in a Docker container on a Raspberry Pi 4.

## Prerequisites

1. Raspberry Pi 4 Model B with Raspberry Pi OS (32-bit or 64-bit)
2. Docker and Docker Compose installed
3. USB camera or Raspberry Pi Camera module
4. (Optional) Google Sheets credentials JSON file for data logging

## Quick Start

The easiest way to run the application is using Docker Compose:

```bash
# Clone the repository (if you haven't already)
git clone <your-repo-url>
cd boat-counter

# Run with Docker Compose
docker-compose up -d
```

To stop the container:

```bash
docker-compose down
```

## Manual Setup with docker-run.sh

Alternatively, you can use the provided `docker-run.sh` script:

```bash
# Make the script executable (if not already)
chmod +x docker-run.sh

# Run the script
./docker-run.sh
```

## Configuration

### Camera Setup

By default, the application uses camera index 0 (`/dev/video0`). If your camera is at a different location, you need to update:

1. The `VIDEO_SOURCE` variable in `boat_counter_full_debug-10.py`
2. The device mapping in `docker-compose.yml` and `docker-run.sh`

### Google Sheets Integration

To enable Google Sheets logging:

1. Place your Google Sheets service account JSON file in the root directory as `gsheets_creds.json`
2. Update the `GSHEET_NAME` variable in the Python script if needed

### Region of Interest Mask

To use a region of interest mask:

1. Create a black and white image where white areas indicate regions to analyze
2. Save it as `mask.png` in the root directory

## Building the Docker Image Manually

If you need to build the Docker image manually:

```bash
docker build -t boat-counter:latest .
```

## Troubleshooting

### Camera Access Issues

If the container can't access the camera:

```bash
# Check if the camera is detected
vcgencmd get_camera

# List video devices
ls -l /dev/video*

# Make sure the device permissions are correct
sudo chmod 666 /dev/video0
```

### Display Issues

For display issues when using the HDMI output:

```bash
# Allow X11 connections from root
xhost +local:root

# Then run the container
```

### Log Files

Check the logs for issues:

```bash
# View container logs
docker logs boat-counter-app

# Check application logs in the logs directory
cat logs/boat_counter.log
```

## Performance Tips

- The YOLOv8n (nano) model is recommended for better performance on Raspberry Pi
- Consider lowering the resolution or frame rate if performance is an issue
- Run in headless mode (disable DISPLAY_WINDOW) for better performance

## Notes

- The container is configured to restart automatically unless explicitly stopped
- Images of counted boats are saved to the `snapshots` directory
- Logs are saved to the `logs` directory 