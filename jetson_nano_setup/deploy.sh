#!/bin/bash
# Script to deploy the boat counter to a Jetson Nano

# Default values
JETSON_IP=""
JETSON_USER="jetson"
DEPLOY_DIR="/home/jetson/boat-counter"

# Display help message
show_help() {
    echo "Usage: ./deploy.sh -i <jetson_ip> [-u <user>] [-d <directory>]"
    echo ""
    echo "Options:"
    echo "  -i, --ip       IP address of the Jetson Nano (required)"
    echo "  -u, --user     SSH username (default: jetson)"
    echo "  -d, --dir      Deployment directory (default: /home/jetson/boat-counter)"
    echo "  -h, --help     Show this help message"
    echo ""
}

# Parse command line arguments
while [ "$1" != "" ]; do
    case $1 in
        -i | --ip )           shift
                              JETSON_IP=$1
                              ;;
        -u | --user )         shift
                              JETSON_USER=$1
                              ;;
        -d | --dir )          shift
                              DEPLOY_DIR=$1
                              ;;
        -h | --help )         show_help
                              exit 0
                              ;;
        * )                   echo "Unknown parameter: $1"
                              show_help
                              exit 1
    esac
    shift
done

# Check if IP address is provided
if [ -z "$JETSON_IP" ]; then
    echo "Error: Jetson Nano IP address is required."
    show_help
    exit 1
fi

# Confirm deployment
echo "Preparing to deploy to Jetson Nano at $JETSON_IP..."
echo "User: $JETSON_USER"
echo "Directory: $DEPLOY_DIR"
read -p "Continue? (y/n) " -n 1 -r
echo    # Move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Create the necessary files
echo "Creating deployment directory on Jetson Nano..."
ssh $JETSON_USER@$JETSON_IP "mkdir -p $DEPLOY_DIR/jetson_nano_setup $DEPLOY_DIR/snapshots $DEPLOY_DIR/src $DEPLOY_DIR/models $DEPLOY_DIR/config"

# Copy the files
echo "Copying files to Jetson Nano..."
scp -r ../src/A2_boat_counter_test_full_cooldown.py ../src/sort.py $JETSON_USER@$JETSON_IP:$DEPLOY_DIR/src/
scp -r ../models/yolov8n.pt $JETSON_USER@$JETSON_IP:$DEPLOY_DIR/models/
scp -r ../config/gsheets_creds.json $JETSON_USER@$JETSON_IP:$DEPLOY_DIR/config/
scp -r ./Dockerfile ./docker-compose.yml ./README.md $JETSON_USER@$JETSON_IP:$DEPLOY_DIR/jetson_nano_setup/

# Optional: copy mask if it exists
if [ -f "../mask.png" ]; then
    echo "Copying mask.png..."
    scp ../mask.png $JETSON_USER@$JETSON_IP:$DEPLOY_DIR/
fi

echo "Starting the container on Jetson Nano..."
ssh $JETSON_USER@$JETSON_IP "cd $DEPLOY_DIR/jetson_nano_setup && docker-compose up -d"

echo "Deployment completed!"
echo "To check the logs, run: ssh $JETSON_USER@$JETSON_IP \"docker logs -f boat-counter\"" 