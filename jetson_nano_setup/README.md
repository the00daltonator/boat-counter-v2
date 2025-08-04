# Boat Counter for Jetson Nano

This directory contains Docker setup files to run the Boat Counter application on a NVIDIA Jetson Nano.

## Repository Structure Note

The repository has been reorganized with a more structured layout:
- Source code is now in the `src/` directory
- Model files are in the `models/` directory
- Configuration files are in the `config/` directory

The Docker setup and scripts in this directory have been updated to work with this new structure.

## Prerequisites

- NVIDIA Jetson Nano with JetPack 4.6 or later
- Docker and Docker Compose installed on Jetson Nano
- Camera connected to the Jetson Nano
- Google Sheets API credentials (for logging)

## Setup Instructions

1. Install Docker on your Jetson Nano if not already installed:

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io
```

2. Install Docker Compose:

```bash
sudo apt-get install -y python3-pip
sudo pip3 install docker-compose
```

3. Add your user to the docker group to run Docker without sudo:

```bash
sudo usermod -aG docker $USER
```
(Logout and log back in for this to take effect)

4. Ensure the YOLO model and Google Sheets credentials are in the root directory:
   - `models/yolov8n.pt`
   - `config/gsheets_creds.json`

5. Optional: Create a `mask.png` file if you want to define a specific region of interest.

## Running the Boat Counter

From the repository root directory:

```bash
cd jetson_nano_setup
docker-compose up -d
```

This will build and start the container in detached mode. The boat counter will start running automatically, processing the video feed and counting boats.

## Checking the Logs

To see the logs from the running container:

```bash
docker logs -f boat-counter
```

## Stopping the Boat Counter

To stop the container:

```bash
docker-compose down
```

## Configuration

You can modify the following environment variables in the `docker-compose.yml` file:

- `VIDEO_DEVICE_INDEX`: The index of the camera device (default: 0)
- `DISPLAY_WINDOW`: Whether to display the video output (set to true only if you have X11 forwarding set up)

## Accessing the Snapshots

The snapshots of detected boats are stored in the `snapshots` directory in your repository root. Each snapshot is named with a timestamp and saved when a boat crosses the counting line.

## Troubleshooting

1. **Camera access issues**:
   - Make sure the camera is properly connected
   - Check that `/dev/video0` exists on your Jetson Nano
   - Adjust the volume mapping in `docker-compose.yml` if your camera is at a different path

2. **Performance issues**:
   - The Jetson Nano has limited resources. Consider lowering the resolution in the script if performance is slow.

3. **Google Sheets connectivity**:
   - Ensure your `gsheets_creds.json` file is valid and has the necessary permissions
   - Check the container logs for any connectivity errors 