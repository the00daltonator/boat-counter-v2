#!/bin/bash
# Helper script to run the boat counter application

# Set default variables
DISPLAY_WINDOW=${DISPLAY_WINDOW:-true}
VIDEO_DEVICE_INDEX=${VIDEO_DEVICE_INDEX:-0}

# Check command line arguments
while [ "$1" != "" ]; do
    case $1 in
        --no-display )    DISPLAY_WINDOW=false
                          ;;
        --device )        shift
                          VIDEO_DEVICE_INDEX=$1
                          ;;
        --help | -h )     echo "Usage: ./run.sh [options]"
                          echo ""
                          echo "Options:"
                          echo "  --no-display         Run without visual display"
                          echo "  --device INDEX       Set video device index (default: 0)"
                          echo "  --help, -h           Show this help message"
                          echo ""
                          exit 0
                          ;;
        * )               echo "Unknown parameter: $1"
                          echo "Use --help for usage information."
                          exit 1
    esac
    shift
done

# Export environment variables
export DISPLAY_WINDOW=$DISPLAY_WINDOW
export VIDEO_DEVICE_INDEX=$VIDEO_DEVICE_INDEX

# Run the boat counter application
echo "Starting boat counter with VIDEO_DEVICE_INDEX=$VIDEO_DEVICE_INDEX and DISPLAY_WINDOW=$DISPLAY_WINDOW"
python src/A2_boat_counter_test_full_cooldown.py 