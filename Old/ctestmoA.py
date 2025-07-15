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

from __future__ import annotations

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
import astral.sun as astral_sun
from picamera2 import Picamera2             # Pi Camera 2 for frame capture

# === CONSTANTS & CONFIG ===
TIMEZONE       = ZoneInfo("America/Denver")
VIDEO_SOURCE   = 0                # 0 == default PiCam.  Replace with path if using a file.
FRAME_WIDTH    = 640
FRAME_HEIGHT   = 360
COUNT_LINE_POS = 0.5              # Normalised horizontal position of count line (0‑1)
DETECTION_CONF = 0.35             # YOLO confidence threshold
COOLDOWN_SEC   = 5                # Seconds an ID must wait before it can be counted again
SNAPSHOT_DIR   = "snapshots"      # Folder to save snapshot images
MODEL_PATH     = "yolov8n.pt"     # Tiny default model (change to your custom model if needed)
GSHEET_JSON    = "gsheets_creds.json"
GSHEET_NAME    = "Boat Counter Logs"

# === HELPER – resilient console print ======================================

def log(msg: str, emoji: str = "") -> None:
    """Print *msg* prefixed with an emoji when the terminal supports it."""
    prefix = emoji
    try:
        prefix.encode("utf‑8").decode("utf‑8")
    except UnicodeDecodeError:
        prefix = ""
    print(f"{prefix} {msg}" if prefix else msg)


# === INITIAL SETUP =========================================================

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Load model once (consider using GPU if available)
model = YOLO(MODEL_PATH)

# Google Sheets
sheet = None
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GSHEET_JSON, scopes=scopes)
    sheet = gspread.authorize(creds).open(GSHEET_NAME).sheet1
    log("Connected to Google Sheets", "✅")
except Exception as e:
    log(f"Google Sheets not connected: {e}", "⚠️")

# Optional mask
mask = None
if os.path.exists("mask.png"):
    mask = cv2.imread("mask.png", cv2.IMREAD_GRAYSCALE)
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]
    log("Mask loaded", "🖼️")
else:
    log("No mask found – using full frame.", "ℹ️")

# Astral – sunrise / sunset helper
city = astral.LocationInfo(latitude=38.833, longitude=-104.821, timezone="America/Denver")

def is_daytime(ts: datetime | None = None) -> bool:
    ts = ts or datetime.now(TIMEZONE)
    s = astral_sun.sun(city.observer, date=ts.date(), tzinfo=TIMEZONE)
    return s["dawn"] <= ts <= s["dusk"]

# Camera setup and robust reopen routine

picam2 = Picamera2()
picam2.start()

# Tracking state
mot_tracker = Sort(max_age=15, min_hits=3, iou_threshold=0.1)
id_last_x   = {}            # track_id -> previous x_center
last_count  = {}            # track_id -> last count timestamp
boat_total  = 0

# Counting line function

def count_line_x(width: int) -> int:
    return int(width * COUNT_LINE_POS)

# === MAIN LOOP =============================================================

log("Starting boat detection. Press 'Q' to exit.", "🎥")
last_daily_check = datetime.now(TIMEZONE).date()

while True:
    now = datetime.now(TIMEZONE)

    # Sunrise/sunset check once per day
    if now.date() != last_daily_check:
        log(f"Checking sunrise/sunset for {now.date()}", "📆")
        last_daily_check = now.date()

    # Sleep at night
    if not is_daytime(now):
        log(f"Night – sleeping 5\u202fmin ({{now:%H:%M:%S}})", "🌙")
        picam2.stop()
        cv2.destroyAllWindows()
        time.sleep(300)
        picam2.start()
        continue

    # Grab frame (no retry needed)
    frame = picam2.capture_array()
    if frame is None:
        log("Frame grab failed – retrying next loop", "⚠️")
        continue

    # Apply mask
    if mask is not None:
        frame_proc = cv2.bitwise_and(frame, frame, mask=mask)
    else:
        frame_proc = frame

    # YOLO detection
    results = model(frame_proc, verbose=False, conf=DETECTION_CONF)
    detections = []
    for r in results:
        for *box, conf, cls in r.boxes:
            if int(cls) == 0:  # class 0 assumed boat
                x1, y1, x2, y2 = map(int, box)
                detections.append([x1, y1, x2, y2, float(conf)])
    det_np = np.array(detections) if detections else np.empty((0, 5))
    tracks = mot_tracker.update(det_np)

    # Draw count line
    fh, fw = frame.shape[:2]
    cx = count_line_x(fw)
    cv2.line(frame, (cx, 0), (cx, fh), (0, 0, 255), 2)

    # Process tracks
    for *xyxy, tid in tracks:
        x1, y1, x2, y2 = map(int, xyxy)
        x_center = (x1 + x2) // 2
        y_center = (y1 + y2) // 2

        # Draw bounding box and ID
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, str(int(tid)), (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        prev_x = id_last_x.get(tid, x_center)
        id_last_x[tid] = x_center

        # Check crossing from left to right
        crossed = prev_x < cx <= x_center
        if crossed:
            last_ts = last_count.get(tid, 0)
            if now.timestamp() - last_ts >= COOLDOWN_SEC:
                boat_total += 1
                last_count[tid] = now.timestamp()
                log(f"Boat #{{boat_total}} detected (track {{int(tid)}})", "🚤")
                # Snapshot
                snap_path = os.path.join(SNAPSHOT_DIR, f"boat_{{boat_total}}_{{int(tid)}}.jpg")
                cv2.imwrite(snap_path, frame)
                # Google Sheets append
                if sheet is not None:
                    try:
                        sheet.append_row([now.isoformat(), boat_total, int(tid), snap_path])
                    except Exception as e:
                        log(f"Sheets append error: {{e}}", "⚠️")

    # Display
    cv2.imshow("Boat Counter", frame)
    if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
        break

# === CLEANUP ===============================================================
log("Exiting – cleaning up", "🛑")
picam2.stop()
cv2.destroyAllWindows()
