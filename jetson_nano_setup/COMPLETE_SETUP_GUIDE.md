# Complete Jetson Nano Setup Guide for Boat Counter

This guide walks through the complete process of setting up a Jetson Nano to run the boat counter application, starting from a fresh Jetson Nano.

## 1. Initial Jetson Nano Setup

If your Jetson Nano is brand new:

1. **Flash the SD card** with the latest JetPack (recommend JetPack 4.6 which uses Ubuntu 18.04):
   - Download the [SD Card Image](https://developer.nvidia.com/jetson-nano-sd-card-image)
   - Use [balenaEtcher](https://www.balena.io/etcher/) to flash the image to your SD card
   - Insert the SD card into the Jetson Nano

2. **Initial boot setup**:
   - Connect keyboard, mouse, and monitor
   - Power on the Jetson Nano
   - Complete the setup wizard (language, timezone, user account, etc.)
   - Connect to your Wi-Fi or Ethernet

3. **Update the system**:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

4. **Enable the camera** (if using CSI camera):
   ```bash
   sudo apt-get install v4l-utils
   v4l2-ctl --list-devices  # To verify camera is detected
   ```

## 2. Install Docker and Prerequisites

1. **Install Docker**:
   ```bash
   # Add Docker's official GPG key
   sudo apt-get update
   sudo apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
   
   # Add Docker repository
   sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
   
   # Install Docker
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io
   
   # Add your user to docker group
   sudo usermod -aG docker $USER
   ```

2. **Install Docker Compose**:
   ```bash
   sudo apt-get install -y python3-pip
   sudo pip3 install docker-compose
   ```
   
   Log out and log back in for group changes to take effect.

3. **Install Git** (if not already installed):
   ```bash
   sudo apt-get install -y git
   ```

## 3. Clone the Repository and Set Up

1. **Clone the repository**:
   ```bash
   cd ~
   git clone https://github.com/your-username/boat-counter.git
   cd boat-counter
   ```

2. **Download YOLOv8 model** (if not included in repo):
   ```bash
   wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
   ```

3. **Create Google Sheets credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the Google Sheets API and Drive API
   - Create a service account
   - Download the credentials as JSON
   - Rename to `gsheets_creds.json` and place in the repository root

4. **Optional: Create a mask image**:
   If you want to limit detection to a specific area:
   - Create a black and white PNG image the same size as your video frame
   - White areas are where detection happens, black areas are ignored
   - Name it `mask.png` and place it in the repository root

## 4. Deploy the Boat Counter

Navigate to the jetson_nano_setup directory:

```bash
cd ~/boat-counter/jetson_nano_setup
```

### Option 1: Build and run on the Jetson directly

```bash
docker-compose up -d
```

### Option 2: If deploying from another machine

On the other machine:

```bash
./deploy.sh -i <jetson-nano-ip-address> -u <username>
```

## 5. Verify and Monitor

1. **Check if the container is running**:
   ```bash
   docker ps
   ```

2. **Monitor the logs**:
   ```bash
   docker logs -f boat-counter
   ```

3. **Check for snapshots**:
   ```bash
   ls -la ~/boat-counter/snapshots/
   ```

## 6. Configure Camera Source

If you need to use a different camera:

1. **Check available video devices**:
   ```bash
   ls -la /dev/video*
   ```

2. **Modify docker-compose.yml**:
   - Update the `VIDEO_DEVICE_INDEX` environment variable
   - Update the volume mount for the video device

## 7. Troubleshooting

1. **Camera not detected**:
   - Ensure camera is properly connected
   - Check permissions: `sudo chmod 666 /dev/video0`

2. **Performance issues**:
   - Check CPU/memory usage: `htop`
   - Consider reducing resolution in the Python script
   - Monitor GPU usage: `sudo tegrastats`

3. **Docker permission issues**:
   ```bash
   sudo chmod 666 /var/run/docker.sock
   ```

4. **Google Sheets errors**:
   - Ensure the service account has been given access to your Google Sheet
   - Check internet connectivity

## 8. Starting on Boot

To automatically start the boat counter on boot:

```bash
crontab -e
```

Add this line:

```
@reboot cd ~/boat-counter/jetson_nano_setup && docker-compose up -d
```

## 9. Updating the Application

To update to the latest version:

```bash
cd ~/boat-counter
git pull
cd jetson_nano_setup
docker-compose down
docker-compose build --no-cache
docker-compose up -d
``` 