#!/bin/bash
# Boat Counter for Jetson Nano - One-command installation script

# Text formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Print header
echo -e "${BOLD}🚢 Boat Counter for Jetson Nano - Installation Script${NC}"
echo "========================================================"
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo -e "${RED}Error: This script must be run on a Jetson device.${NC}"
    exit 1
fi

# Function to display status messages
status() {
    echo -e "${YELLOW}⏳ $1...${NC}"
}

# Function to display success messages
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to display error messages and exit
error() {
    echo -e "${RED}❌ Error: $1${NC}"
    exit 1
}

# Ask for repository details
read -p "GitHub username (default: your-username): " github_user
github_user=${github_user:-your-username}

# Install dependencies
status "Updating system packages"
sudo apt update && sudo apt upgrade -y || error "Failed to update system packages"
success "System updated"

status "Installing prerequisites"
sudo apt install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common git v4l-utils || error "Failed to install prerequisites"
success "Prerequisites installed"

# Install Docker
status "Installing Docker"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io || error "Failed to install Docker"
    sudo usermod -aG docker $USER
    success "Docker installed"
else
    success "Docker already installed"
fi

# Install Docker Compose
status "Installing Docker Compose"
if ! command -v docker-compose &> /dev/null; then
    sudo apt install -y python3-pip
    sudo pip3 install docker-compose || error "Failed to install Docker Compose"
    success "Docker Compose installed"
else
    success "Docker Compose already installed"
fi

# Clone repository
status "Cloning boat-counter repository"
mkdir -p ~/boat-counter
cd ~/boat-counter
if [ ! -d .git ]; then
    git clone https://github.com/$github_user/boat-counter.git . || error "Failed to clone repository"
    success "Repository cloned"
else
    git pull
    success "Repository updated"
fi

# Create directory structure
status "Setting up directory structure"
mkdir -p src models config snapshots
success "Directories created"

# Download YOLOv8 model if not present
status "Checking for YOLOv8 model"
if [ ! -f models/yolov8n.pt ]; then
    status "Downloading YOLOv8 model"
    wget -P models/ https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt || error "Failed to download YOLOv8 model"
    success "YOLOv8 model downloaded"
else
    success "YOLOv8 model already exists"
fi

# Check for Google Sheets credentials
status "Checking for Google Sheets credentials"
if [ ! -f config/gsheets_creds.json ]; then
    echo -e "${YELLOW}⚠️ Warning: config/gsheets_creds.json not found${NC}"
    echo "You'll need to provide Google Sheets credentials to log boat counts."
    echo "Place the credentials file at ~/boat-counter/config/gsheets_creds.json"
else
    success "Google Sheets credentials found"
fi

# Create symbolic links for backward compatibility
status "Creating compatibility symlinks"
ln -sf models/yolov8n.pt yolov8n.pt
ln -sf config/gsheets_creds.json gsheets_creds.json
success "Symlinks created"

# Build and start container
status "Building and starting boat counter container"
cd ~/boat-counter/jetson_nano_setup
docker-compose up -d || error "Failed to start container"
success "Container started"

# Verify running
if docker ps | grep -q boat-counter; then
    success "Boat counter is now running!"
    echo ""
    echo -e "${BOLD}📊 Boat Counter Status:${NC}"
    echo "----------------------------------------"
    echo "🔍 Check logs:    docker logs -f boat-counter"
    echo "⏹️ Stop service:  cd ~/boat-counter/jetson_nano_setup && docker-compose down"
    echo "🔄 Restart:       cd ~/boat-counter/jetson_nano_setup && docker-compose restart"
    echo "📷 Snapshots:     ~/boat-counter/snapshots/"
    echo ""
    echo "Auto-start on boot? Run: (y/n)"
    read -p "Add to crontab for automatic startup on boot? (y/n): " auto_start
    if [[ $auto_start == "y" || $auto_start == "Y" ]]; then
        (crontab -l 2>/dev/null; echo "@reboot cd ~/boat-counter/jetson_nano_setup && docker-compose up -d") | crontab -
        success "Added to crontab - will start automatically on boot"
    fi
else
    echo -e "${YELLOW}⚠️ Container not detected - check logs with:${NC}"
    echo "docker logs boat-counter"
fi

# Print final message
echo ""
echo -e "${BOLD}🚢 Boat Counter installation complete!${NC}"
echo "========================================================"
echo -e "${YELLOW}Note: You may need to log out and log back in for docker permissions to take effect.${NC}"
echo "" 