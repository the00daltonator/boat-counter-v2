# Boat Counter

A computer vision application that detects and counts boats in video streams using YOLOv8 and SORT (Simple Online and Realtime Tracking).

## Features

- Real-time boat detection using YOLOv8
- Object tracking with SORT algorithm
- Line crossing detection for counting
- Visual debugging with bounding boxes and tracking IDs
- Automatic snapshot capture of detected boats
- Google Sheets integration for data logging
- Docker support for easy deployment
- Jetson Nano compatibility

## Repository Structure

```
boat-counter/
├── config/               # Configuration files
│   ├── gsheets_creds.json
│   ├── gsheets_creds_template.json
│   ├── requirements.txt
│   └── requirements_new.txt
├── docker/               # Docker setup for general use
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-run.sh
│   └── README-Docker.md
├── docs/                 # Documentation
├── jetson_nano_setup/    # Jetson Nano specific setup
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── install.sh
│   ├── COMPLETE_SETUP_GUIDE.md
│   ├── QUICK_INSTALL.md
│   └── README.md
├── models/               # Model files
│   └── yolov8n.pt
├── snapshots/            # Boat detection snapshots
├── src/                  # Source code
│   ├── A2_boat_counter_test_full_cooldown.py
│   ├── boat_counter_full_debug-10.py
│   └── sort.py
└── tests/                # Test data
    └── test_boats3.mp4
```

## Requirements

- Python 3.7+
- OpenCV
- Ultralytics (YOLOv8)
- NumPy
- Optional: Docker for containerized deployment
- Optional: NVIDIA Jetson Nano for embedded deployment

## Installation

### Standard Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd boat-counter
```

2. Install dependencies:
```bash
pip install -r config/requirements.txt
```

3. Download the YOLOv8 model (if not already in models/ directory):
```bash
# The yolov8n.pt model should download automatically when needed
# or you can download it manually from the Ultralytics repository
```

4. Set up Google Sheets integration (optional):
   - See `config/README.md` for instructions
   - Use `config/gsheets_creds_template.json` as a template
   - Rename your credentials file to `gsheets_creds.json`

### Docker Installation

See instructions in `docker/README-Docker.md` for deploying with Docker.

### Jetson Nano Installation

For deploying on a Jetson Nano, we provide a complete setup:

1. Quick installation (on the Jetson Nano):
```bash
curl -fsSL https://raw.githubusercontent.com/your-username/boat-counter/main/jetson_nano_setup/install.sh | bash
```

2. Manual installation:
   - See `jetson_nano_setup/COMPLETE_SETUP_GUIDE.md` for detailed instructions
   - See `jetson_nano_setup/QUICK_INSTALL.md` for a quick reference

## Usage

1. Run the main application:
```bash
python src/A2_boat_counter_test_full_cooldown.py
```
Or use the helper script:
```bash
./run.sh
```

2. Configure video source:
   - Set `VIDEO_DEVICE_INDEX` environment variable or modify in the script
   - Default is camera index 0

3. Optional: Create a mask to define detection region
   - Create a black and white PNG image named "mask.png" in the repository root
   - White areas are where detection happens, black areas are ignored

## Configuration

Key parameters in the main script:

- `VIDEO_SOURCE`: Camera index or video file path
- `MODEL_PATH`: Path to YOLO model file 
- `CLASS_FILTER`: Object class to detect ("boat")
- `CONFIDENCE_THRESHOLD`: Minimum confidence for detection (0.15)
- `COUNT_LINE`: Line coordinates for counting [x1, y1, x2, y2]
- `SNAPSHOT_DIR`: Directory to save boat snapshots
- `GSHEET_CREDS_FILE`: Path to Google Sheets credentials
- `COOLDOWN_SECONDS`: Cooldown period to prevent duplicate counts

## License

[Add your license here] 