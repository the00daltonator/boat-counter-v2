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
import cv2  # For video frame processing and GUI
import numpy as np  # For working with arrays and matrices
import math  # For rounding and mathematical operations
import time  # For timing intervals
import os  # For file system access
from datetime import datetime  # For timestamps
from ultralytics import YOLO  # YOLOv8 object detection model
from sort import *  # SORT = Simple Online and Realtime Tracking
import gspread  # Google Sheets Python API
from google.oauth2.service_account import Credentials  # Google auth with service accounts

# === CONFIGURATION SECTION ===
VIDEO_SOURCE = "test_boats4.mp4"
MODEL_PATH = "yolov8n.pt"
CLASS_FILTER = "boat"
CONFIDENCE_THRESHOLD = 0.3
SNAPSHOT_DIR = "snapshots"
GSHEET_CREDS_FILE = "gsheets_creds.json"
GOOGLE_SHEET_NAME = "Boat Counter Logs"

# === SETUP GOOGLE SHEETS CONNECTION ===
sheet = None
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(GSHEET_CREDS_FILE, scopes=scopes)
    client = gspread.authorize(credentials)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    print("[✅] Connected to Google Sheets")
    print("[🧪] Test A1 value:", sheet.acell('A1').value)
except Exception as e:
    print(f"[⚠️ WARN] Google Sheets not connected: {e}")

# === OPTIONAL MASK LOADING ===
mask = None
if os.path.exists("mask.png"):
    mask = cv2.imread("mask.png", cv2.IMREAD_GRAYSCALE)
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]
    print("[🧭] Mask loaded successfully.")
else:
    print("[ℹ️] No mask found – using full frame.")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# === LOAD VIDEO AND MODEL ===
cap = cv2.VideoCapture(VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
line_x = frame_width // 4
COUNT_LINE = [line_x, 0, line_x, frame_height]

model = YOLO(MODEL_PATH)
tracker = Sort(max_age=30, min_hits=5, iou_threshold=0.5)

totalCount = []
counted_ids = set()
id_history = {}  # Track recent centroids

print("[🎥] Starting boat detection test. Press 'Q' to exit.")

# === MAIN LOOP ===
while True:
    success, img = cap.read()
    if not success:
        print("[✅] Finished processing video.")
        break

    imgMasked = cv2.bitwise_and(img, img, mask=mask) if mask is not None else img

    # === OBJECT DETECTION ===
    detections = np.empty((0, 5))
    results = model(imgMasked, stream=True)
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = math.ceil((box.conf[0] * 100)) / 100
            cls = int(box.cls[0])
            currentClass = model.names[cls]
            if currentClass == CLASS_FILTER and conf > CONFIDENCE_THRESHOLD:
                detections = np.vstack((detections, [x1, y1, x2, y2, conf]))

    # === OBJECT TRACKING ===
    resultsTracker = tracker.update(detections)
    for result in resultsTracker:
        x1, y1, x2, y2, id = map(int, result)
        cx, cy = x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2
        center = (cx, cy)

        if id not in id_history:
            id_history[id] = []
        id_history[id].append(center)

        if len(id_history[id]) > 10:
            id_history[id] = id_history[id][-10:]

        if len(id_history[id]) >= 2:
            x_positions = [pt[0] for pt in id_history[id]]
            crossed = any(
                (x_positions[i] < COUNT_LINE[0] < x_positions[i + 1]) or
                (x_positions[i] > COUNT_LINE[0] > x_positions[i + 1])
                for i in range(len(x_positions) - 1)
            )
            if crossed and id not in counted_ids:
                counted_ids.add(id)
                totalCount.append(id)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                print(f"[✅] Boat #{id} counted at {timestamp}")
                filename = f"boat_{timestamp}.jpg"
                filepath = os.path.join(SNAPSHOT_DIR, filename)
                cv2.imwrite(filepath, img)
                if sheet:
                    now = datetime.now()
                    try:
                        sheet.append_row([
                            now.strftime('%Y-%m-%d'),
                            now.strftime('%H:%M:%S'),
                            len(totalCount),
                            filename
                        ])
                    except Exception as e:
                        print(f"[❌ ERROR] Google Sheets write failed: {e}")

        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 2)
        cv2.putText(img, f"ID: {id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
        cv2.circle(img, (cx, cy), 5, (0, 255, 255), -1)

    cv2.line(img, (COUNT_LINE[0], COUNT_LINE[1]), (COUNT_LINE[2], COUNT_LINE[3]), (0, 0, 255), 2)
    cv2.putText(img, f"Total: {len(totalCount)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(img, "Press Q to quit", (400, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow("Boat Detection Test", img)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print(f"[🏁 DONE] Final boat count: {len(totalCount)}")
