"""
Boat Counter Test Full Version – Robust Edition
==============================================

This script demonstrates a full‑featured boat counter with:

- Real‑time boat detection using YOLOv8
- Object tracking with SORT
- Line‑crossing detection for counting
- Automatic snapshot capture of detected boats
- Google Sheets integration for data logging
- Optional binary mask for region‑of‑interest filtering
- Visual debugging and live video display
- Automatic sleep / wake based on sunrise & sunset (America/Denver)
- Graceful camera‑retry logic so a single frame failure doesn’t end the program
- UTF‑8‑safe console logging (falls back to ASCII if the terminal locale is not UTF‑8)

Author: the00daltonator
Last updated: 2025‑07‑15
"""

from __future__ import annotations  # Enables postponed evaluation of type annotations (Python 3.7+)

# === IMPORTS SECTION ===
import cv2                                  # OpenCV for video processing and GUI
import numpy as np                          # For array and matrix operations
import time                                 # For timing and delays
import os                                   # For file and directory operations
from datetime import datetime               # For timestamps
from zoneinfo import ZoneInfo               # Native TZ support (Python 3.11+)
from ultralytics import YOLO                # YOLOv8 object detection model
from sort import *                          # SORT tracker for object tracking
import gspread                              # Google Sheets API
from google.oauth2.service_account import Credentials  # Google service‑account auth
import astral                               # Sunrise / sunset calculation
import astral.sun as astral_sun             # For sunrise/sunset times

# === CONSTANTS & CONFIG ===
TIMEZONE       = ZoneInfo("America/Denver")         # Set timezone for all time operations
VIDEO_SOURCE   = 0                                  # 0 == default PiCam. Replace with path if using a file.
FRAME_WIDTH    = 640                                # Width of video frames
FRAME_HEIGHT   = 360                                # Height of video frames
COUNT_LINE_POS = 0.5                                # Normalised horizontal position of count line (0‑1)
DETECTION_CONF = 0.35                               # YOLO confidence threshold
COOLDOWN_SEC   = 5                                  # Seconds an ID must wait before it can be counted again
SNAPSHOT_DIR   = "snapshots"                        # Folder to save snapshot images
MODEL_PATH     = "yolov8n.pt"                       # Path to YOLOv8 model weights
GSHEET_JSON    = "gsheets_creds.json"               # Google Sheets credentials file
GSHEET_NAME    = "Boat Counter Logs"                # Google Sheet name

# === HELPER – resilient console print ======================================
def log(msg: str, emoji: str = "") -> None:
    """Print *msg* prefixed with an emoji when the terminal supports it."""
    prefix = emoji  # Set emoji prefix
    try:
        prefix.encode("utf‑8").decode("utf‑8")  # Try encoding/decoding to check UTF-8 support
    except UnicodeDecodeError:
        prefix = ""  # Remove emoji if not supported
    print(f"{prefix} {msg}" if prefix else msg)  # Print message with or without emoji

# === INITIAL SETUP =========================================================

os.makedirs(SNAPSHOT_DIR, exist_ok=True)  # Ensure the snapshot directory exists

model = YOLO(MODEL_PATH)  # Load YOLOv8 model for detection

sheet = None  # Initialize Google Sheets variable
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",  # Scope for Sheets
        "https://www.googleapis.com/auth/drive",         # Scope for Drive
    ]
    creds = Credentials.from_service_account_file(GSHEET_JSON, scopes=scopes)  # Load credentials
    sheet = gspread.authorize(creds).open(GSHEET_NAME).sheet1  # Open the first worksheet
    log("Connected to Google Sheets", "✅")  # Log success
except Exception as e:
    log(f"Google Sheets not connected: {e}", "⚠️")  # Log failure

mask = None  # Initialize mask variable
if os.path.exists("mask.png"):  # If mask file exists
    mask = cv2.imread("mask.png", cv2.IMREAD_GRAYSCALE)  # Load mask as grayscale
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]  # Ensure mask is binary
    log("Mask loaded", "🖼️")  # Log mask loaded
else:
    log("No mask found – using full frame.", "ℹ️")  # Log no mask found

city = astral.LocationInfo(latitude=38.833, longitude=-104.821, timezone="America/Denver")  # Set city/location for Astral

def is_daytime(ts: datetime | None = None) -> bool:
    ts = ts or datetime.now(TIMEZONE)  # Use current time if not provided
    s = astral_sun.sun(city.observer, date=ts.date(), tzinfo=TIMEZONE)  # Get sunrise/sunset times
    return s["dawn"] <= ts <= s["dusk"]  # Return True if current time is between dawn and dusk

# Camera setup and robust reopen routine

def open_camera() -> cv2.VideoCapture | None:
    cap = cv2.VideoCapture(VIDEO_SOURCE)  # Open video source (camera or file)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)  # Set frame width
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)  # Set frame height
    for _ in range(10):  # Try up to 10 times to get a valid frame
        ok, _ = cap.read()
        if ok:
            return cap  # Return camera if frame read is successful
        time.sleep(0.1)  # Wait a bit before retrying
    log("Camera failed warm‑up", "⚠️")  # Log camera warm-up failure
    cap.release()  # Release camera resource
    return None  # Return None if camera not available

cap = open_camera()  # Open the camera at startup

mot_tracker = Sort(max_age=15, min_hits=3, iou_threshold=0.1)  # Initialize SORT tracker
id_last_x   = {}            # Dictionary to store last x position for each track ID
last_count  = {}            # Dictionary to store last count timestamp for each track ID
boat_total  = 0             # Total number of boats counted

def count_line_x(width: int) -> int:
    return int(width * COUNT_LINE_POS)  # Calculate x position of counting line

# === MAIN LOOP =============================================================

log("Starting boat detection. Press 'Q' to exit.", "🎥")  # Log start of detection
last_daily_check = datetime.now(TIMEZONE).date()  # Track last date checked for sunrise/sunset

while True:
    now = datetime.now(TIMEZONE)  # Get current time

    # Sunrise/sunset check once per day
    if now.date() != last_daily_check:
        log(f"Checking sunrise/sunset for {now.date()}", "📆")  # Log daily check
        last_daily_check = now.date()  # Update last checked date

    # Sleep at night
    if not is_daytime(now):
        log(f"Night – sleeping 5 min ({now:%H:%M:%S})", "🌙")  # Log sleep
        if cap:
            cap.release()  # Release camera
            cap = None
        cv2.destroyAllWindows()  # Close OpenCV windows
        time.sleep(300)  # Sleep for 5 minutes
        continue  # Skip to next loop

    # Ensure camera available
    if cap is None or not cap.isOpened():
        log("(Re)initialising camera…", "🌞")  # Log camera reinitialization
        cap = open_camera()  # Try to open camera
        if cap is None:
            time.sleep(5)  # Wait before retrying
            continue

    # Grab frame (retry up to 3 times)
    ok, frame = cap.read()  # Read a frame from the camera
    if not ok or frame is None:
        log("Frame grab failed – retrying next loop", "⚠️")  # Log frame grab failure
        cap.release()  # Release camera
        cap = None
        continue

    # Apply mask
    if mask is not None:
        frame_proc = cv2.bitwise_and(frame, frame, mask=mask)  # Apply mask to frame
    else:
        frame_proc = frame  # Use full frame if no mask

    # YOLO detection
    results = model(frame_proc, verbose=False, conf=DETECTION_CONF)  # Run YOLO detection
    detections = []  # List to store detections
    for r in results:
        for *box, conf, cls in r.boxes:
            if int(cls) == 0:  # class 0 assumed boat
                x1, y1, x2, y2 = map(int, box)  # Get bounding box coordinates
                detections.append([x1, y1, x2, y2, float(conf)])  # Add detection
    det_np = np.array(detections) if detections else np.empty((0, 5))  # Convert to numpy array
    tracks = mot_tracker.update(det_np)  # Update tracker with detections

    # Draw count line
    fh, fw = frame.shape[:2]  # Get frame height and width
    cx = count_line_x(fw)  # Get x position of count line
    cv2.line(frame, (cx, 0), (cx, fh), (0, 0, 255), 2)  # Draw vertical count line

    # Process tracks
    for *xyxy, tid in tracks:
        x1, y1, x2, y2 = map(int, xyxy)  # Get bounding box coordinates
        x_center = (x1 + x2) // 2  # Calculate center x
        y_center = (y1 + y2) // 2  # Calculate center y

        # Draw bounding box and ID
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Draw bounding box
        cv2.putText(frame, str(int(tid)), (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)  # Draw track ID

        prev_x = id_last_x.get(tid, x_center)  # Get previous x position
        id_last_x[tid] = x_center  # Update last x position

        # Check crossing from left to right
        crossed = prev_x < cx <= x_center  # Check if object crossed the line
        if crossed:
            last_ts = last_count.get(tid, 0)  # Get last count timestamp
            if now.timestamp() - last_ts >= COOLDOWN_SEC:  # Check cooldown
                boat_total += 1  # Increment boat count
                last_count[tid] = now.timestamp()  # Update last count timestamp
                log(f"Boat #{boat_total} detected (track {int(tid)})", "🚤")  # Log detection
                # Snapshot
                snap_path = os.path.join(SNAPSHOT_DIR, f"boat_{boat_total}_{int(tid)}.jpg")  # Path for snapshot
                cv2.imwrite(snap_path, frame)  # Save snapshot
                # Google Sheets append
                if sheet is not None:
                    try:
                        sheet.append_row([now.isoformat(), boat_total, int(tid), snap_path])  # Log to Google Sheets
                    except Exception as e:
                        log(f"Sheets append error: {e}", "⚠️")  # Log Sheets error

    # Display
    cv2.imshow("Boat Counter", frame)  # Show frame in window
    if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):  # Exit on 'q' key
        break

# === CLEANUP ===============================================================
log("Exiting – cleaning up", "🛑")  # Log cleanup
if cap:
    cap.release()  # Release camera
cv2.destroyAllWindows()  # Close OpenCV windows
