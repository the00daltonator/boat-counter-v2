# Boat Counter Quick Install Guide

## 📋 Prerequisites
- Jetson Nano with JetPack 4.6+
- Internet connection
- Camera connected

## 🚀 One-Command Install Script

```bash
# Run this on your Jetson Nano
curl -fsSL https://raw.githubusercontent.com/your-username/boat-counter/main/jetson_nano_setup/install.sh | bash
```

## 🔧 Manual Install Steps

1. **Update system**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Docker**
   ```bash
   sudo apt install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
   sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
   sudo apt update
   sudo apt install -y docker-ce docker-ce-cli containerd.io
   sudo usermod -aG docker $USER
   ```
   *Log out and log back in*

3. **Install Docker Compose**
   ```bash
   sudo apt install -y python3-pip
   sudo pip3 install docker-compose
   ```

4. **Clone repository**
   ```bash
   cd ~
   git clone https://github.com/your-username/boat-counter.git
   cd boat-counter
   ```

5. **Get YOLO model** (if not included)
   ```bash
   wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
   ```

6. **Add Google Sheets credentials**
   - Place `gsheets_creds.json` in repository root

7. **Run boat counter**
   ```bash
   cd jetson_nano_setup
   docker-compose up -d
   ```

8. **Monitor**
   ```bash
   docker logs -f boat-counter
   ```

## 📺 Camera Configuration

- Default: `/dev/video0`
- Change in `docker-compose.yml`:
  - Update `VIDEO_DEVICE_INDEX` 
  - Update volume mount for device

## 🛠️ Common Issues

- **Docker permission error**: `sudo chmod 666 /var/run/docker.sock`
- **Camera not found**: Check `ls -la /dev/video*`
- **Google Sheets error**: Check internet and credential permissions

## 🔄 Auto-start on Boot

```bash
crontab -e
```
Add: `@reboot cd ~/boat-counter/jetson_nano_setup && docker-compose up -d` 