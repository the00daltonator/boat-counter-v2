"""
Boat Counter Test Full Version
=============================

This script demonstrates a full-featured boat counter with:
- Real-time boat detection using YOLOv8
- Object tracking with SORT
- Line crossing detection for counting
- Automatic snapshot capture of detected boats
- Google Sheets integration for data logging
- Optional binary mask for region-of-interest filtering
- Visual debugging and live video display

Author: the00daltonator 
Date: 07/09/2025
"""

# === IMPORTS SECTION ===
import cv2  # OpenCV for video processing and GUI
import numpy as np  # For array and matrix operations
import math  # For rounding and math functions
import time  # For timing and delays
import os  # For file and directory operations
from datetime import datetime  # For timestamps
from ultralytics import YOLO  # YOLOv8 object detection model
from sort import *  # SORT tracker for object tracking
import gspread  # Google Sheets API
from google.oauth2.service_account import Credentials  # Google service account auth

# === CONFIGURATION SECTION ===
VIDEO_SOURCE = 0  #"test_boats3.mp4"  # Path to the input video file
MODEL_PATH = "yolov8n.pt"         # Path to YOLOv8 model file
CLASS_FILTER = "boat"             # Only detect and count boats
CONFIDENCE_THRESHOLD = 0.15        # Minimum confidence for detection
SNAPSHOT_DIR = "snapshots"        # Directory to save boat snapshots
GSHEET_CREDS_FILE = "gsheets_creds.json"  # Google Sheets service account file
GOOGLE_SHEET_NAME = "Boat Counter Logs"   # Name of the Google Sheet
COOLDOWN_SECONDS = 5  # Cooldown per boat ID to prevent duplicates
DISPLAY_WINDOW = False  # Set to False when running in Docker/headless mode

# === SETUP GOOGLE SHEETS CONNECTION ===
sheet = None  # Will hold the Google Sheet object if connection is successful
try:
    scopes = [  # Define the required Google API scopes
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(GSHEET_CREDS_FILE, scopes=scopes)  # Load service account credentials from JSON file
    client = gspread.authorize(credentials)  # Authorize and open the specified Google Sheet
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1  # Get the first worksheet
    print("[✅] Connected to Google Sheets")  # Print success message
    print("[🧪] Test A1 value:", sheet.acell('A1').value)  # Print value of cell A1 for test
except Exception as e:
    print(f"[⚠️ WARN] Google Sheets not connected: {e}")  # Print warning if connection fails

# === OPTIONAL MASK LOADING ===
mask = None  # Will hold the binary mask if available
if os.path.exists("mask.png"):  # Check if mask file exists
    mask = cv2.imread("mask.png", cv2.IMREAD_GRAYSCALE)  # Load mask as grayscale
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]  # Ensure mask is binary (0 or 255)
    print("[🧭] Mask loaded successfully.")  # Print success message
else:
    print("[ℹ️] No mask found – using full frame.")  # Print info if no mask

os.makedirs(SNAPSHOT_DIR, exist_ok=True)  # Ensure the snapshot directory exists

# === LOAD VIDEO AND MODEL ===
cap = cv2.VideoCapture(VIDEO_SOURCE)  # Open the video file
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Set width for consistency
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)  # Set height for consistency

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # Get frame width
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))  # Get frame height
line_x = frame_width // 2  # Place the line at 1/2 of the frame width
COUNT_LINE = [line_x, 0, line_x, frame_height]  # Vertical red line from top to bottom

model = YOLO(MODEL_PATH)  # Load YOLOv8 model for detection
tracker = Sort(max_age=30, min_hits=3, iou_threshold=0.4)  # Initialize object tracker

# === TRACKING VARIABLES ===
totalCount = []      # List of unique counted boat IDs
counted_ids = set()  # Set of IDs that have already been counted (prevents double-counting)
id_history = {}      # Dictionary to store the last N centroids for each ID
last_count_time = {} # Dictionary to store the last count time for each ID

print("[🎥] Starting boat detection test. Press 'Q' to exit.")  # Print start message

# === MAIN LOOP ===
while True:  # Loop over video frames
    success, img = cap.read()  # Read a frame from the video
    if not success:  # If no frame is read (end of video)
        print("[✅] Finished processing video.")  # Print finished message
        break  # Exit loop

    imgMasked = cv2.bitwise_and(img, img, mask=mask) if mask is not None else img  # Apply mask if available

    detections = np.empty((0, 5))  # Prepare empty array for detections
    results = model(imgMasked, stream=True)  # Run YOLO on the frame
    for r in results:  # Loop over detection results
        for box in r.boxes:  # Loop over detected boxes
            x1, y1, x2, y2 = map(int, box.xyxy[0])  # Extract bounding box coordinates
            conf = math.ceil((box.conf[0] * 100)) / 100  # Round confidence
            cls = int(box.cls[0])  # Get class index
            currentClass = model.names[cls]  # Get class name
            if currentClass == CLASS_FILTER and conf > CONFIDENCE_THRESHOLD:  # Filter by class and confidence
                detections = np.vstack((detections, [x1, y1, x2, y2, conf]))  # Add detection to array

    # Handle empty detections array properly
    if len(detections) == 0:
        resultsTracker = np.empty((0, 5))
    else:
        resultsTracker = tracker.update(detections)  # Track detected objects
        
    for result in resultsTracker:  # Loop over tracked objects
        x1, y1, x2, y2, id = map(int, result)  # Get bounding box and ID
        cx, cy = x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2  # Center of the box
        center = (cx, cy)  # Store center as tuple

        if id not in id_history:  # If ID not in history, initialize list
            id_history[id] = []
        id_history[id].append(center)  # Add current center to history
        if len(id_history[id]) > 15:  # Keep only last 15 points
            id_history[id] = id_history[id][-15:]

        if len(id_history[id]) >= 2:  # If enough history to check movement
            x_positions = [pt[0] for pt in id_history[id]]  # Get all x positions
            direction = "Right" if x_positions[-1] > x_positions[0] else "Left"  # Determine direction
            crossed = any(  # Check if the line was crossed in either direction
                (x_positions[i] < COUNT_LINE[0] < x_positions[i + 1]) or
                (x_positions[i] > COUNT_LINE[0] > x_positions[i + 1])
                for i in range(len(x_positions) - 1)
            )
            distance = abs(x_positions[-1] - x_positions[0])  # Distance moved

            now = time.time()  # Get current time
            recent = last_count_time.get(id, 0)  # Get last count time for this ID
            if crossed and distance > 15 and (now - recent) > COOLDOWN_SECONDS:  # If crossed, moved enough, and cooldown passed
                counted_ids.add(id)  # Mark as counted
                last_count_time[id] = now  # Update last count time
                totalCount.append(id)  # Add to total count
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')  # Get timestamp
                print(f"[✅] Boat #{id} counted at {timestamp} going {direction}")  # Print count message
                filename = f"boat_{timestamp}.jpg"  # Filename for snapshot
                filepath = os.path.join(SNAPSHOT_DIR, filename)  # Full path
                cv2.imwrite(filepath, img)  # Save the frame as an image
                if sheet:  # If Google Sheets is connected
                    try:
                        sheet.append_row([
                            datetime.now().strftime('%Y-%m-%d'),  # Date
                            datetime.now().strftime('%H:%M:%S'),  # Time
                            len(totalCount),                      # Total count
                            filename,                             # Image filename
                            direction                             # Direction
                        ])
                    except Exception as e:
                        print(f"[❌ ERROR] Google Sheets write failed: {e}")  # Print error if logging fails

        if id in id_history and len(id_history[id]) >= 2:  # If enough history to determine direction
            direction = "Right" if id_history[id][-1][0] > id_history[id][0][0] else "Left"  # Determine direction
        else:
            direction = "???"  # Not enough info to determine

        # Draw visualizations (only if display is enabled)
        if DISPLAY_WINDOW:
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 2)  # Bounding box
            cv2.putText(img, f"ID: {id} {direction}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)  # ID and direction
            cv2.circle(img, (cx, cy), 5, (0, 255, 255), -1)  # Center point
            for pt in id_history[id]:
                cv2.circle(img, pt, 2, (0, 255, 255), -1)  # Trajectory

    # Only add visualization if display is enabled
    if DISPLAY_WINDOW:
        cv2.line(img, (COUNT_LINE[0], COUNT_LINE[1]), (COUNT_LINE[2], COUNT_LINE[3]), (0, 0, 255), 2)  # Counting line
        cv2.putText(img, f"Total: {len(totalCount)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)  # Total count
        cv2.putText(img, "Press Q to quit", (img.shape[1] - cv2.getTextSize("Press Q to quit", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0] - 20, img.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        cv2.imshow("Boat Detection Test", img)  # Show the frame
        if cv2.waitKey(1) & 0xFF == ord("q"):  # Wait for 'q' key to quit
            break

cap.release()  # Release the video capture
if DISPLAY_WINDOW:
    cv2.destroyAllWindows()  # Close all OpenCV windows
print(f"[🏁 DONE] Final boat count: {len(totalCount)}")  # Print final count
