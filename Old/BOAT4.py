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
- Auto sleep mode at night using sunrise/sunset (MST)

Author: the00daltonator
Date: 07/14/2025 
"""

# === IMPORTS SECTION ===
print("[🔁 DEBUG] Importing libraries...")
import cv2
import numpy as np
import math
import time
import os
import socket
from datetime import datetime
from ultralytics import YOLO
from sort import *
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from astral.sun import sun
from astral import LocationInfo
import pytz

# === CONFIGURATION SECTION ===
print("[⚙️ DEBUG] Setting configuration variables...")
VIDEO_SOURCE = "test_boats.mp4" 
MODEL_PATH = "yolov8n.pt"
CLASS_FILTER = "boat"
CONFIDENCE_THRESHOLD = 0.15
SNAPSHOT_DIR = "snapshots"
GSHEET_CREDS_FILE = "gsheets_creds.json"
GOOGLE_SHEET_NAME = "Boat Counter Logs"
COOLDOWN_SECONDS = 5

# === LOCATION CONFIG FOR DAYLIGHT-AWARE MODE ===
CITY = LocationInfo("Colorado Springs", "USA", "MST", 38.8339, -104.8214)
TIMEZONE = pytz.timezone("MST")

# === HELPER FUNCTIONS ===
def is_daytime():
    now = datetime.now(TIMEZONE)
    s = sun(CITY.observer, date=now.date(), tzinfo=TIMEZONE)
    print(f"[🕒 DEBUG] Checking if daytime: Now={now}, Sunrise={s['sunrise']}, Sunset={s['sunset']}")
    return s["sunrise"] <= now <= s["sunset"]

def setup_capture():
    print("[📷 DEBUG] Setting up video capture...")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    return cap

def shutdown_display():
    print("[🌙 DEBUG] Shutting down display...")
    os.system("/usr/bin/tvservice -o")
    os.system("vcgencmd display_power 0")

def wake_display():
    print("[🌞 DEBUG] Waking up display...")
    os.system("/usr/bin/tvservice -p")
    os.system("vcgencmd display_power 1")

def has_internet(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        print(f"[❌ DEBUG] Internet check failed: {e}")
        return False

# === GOOGLE SHEETS CONNECTION ===
print("[🌐 DEBUG] Connecting to Google Sheets...")
sheet = None
if has_internet():
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_file(GSHEET_CREDS_FILE, scopes=scopes)
        credentials.refresh(Request(timeout=5))
        client = gspread.authorize(credentials)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        print("[✅] Connected to Google Sheets")
        print("[🧪] Test A1 value:", sheet.acell('A1').value)
    except Exception as e:
        print(f"[⚠️ WARN] Google Sheets not connected or failed to load: {e}")
else:
    print("[❌] No internet — skipping Google Sheets setup.")

# === OPTIONAL MASK LOADING ===
print("[🖼️ DEBUG] Attempting to load mask.png...")
mask = None
if os.path.exists("mask.png"):
    mask = cv2.imread("mask.png", cv2.IMREAD_GRAYSCALE)
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]
    print("[🧭] Mask loaded successfully.")
else:
    print("[ℹ️] No mask found – using full frame.")

print("[📁 DEBUG] Ensuring snapshot directory exists...")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

print(f"[🧠 DEBUG] Loading YOLO model from {MODEL_PATH}...")
model = YOLO(MODEL_PATH)

print("[🔄 DEBUG] Initializing SORT tracker...")
tracker = Sort(max_age=30, min_hits=3, iou_threshold=0.4)

# === TRACKING VARIABLES ===
print("[📊 DEBUG] Initializing tracking variables...")
totalCount = []
counted_ids = set()
id_history = {}
last_count_time = {}

print("[🎥] Starting boat detection test. Press 'Q' to exit.")

last_checked_day = None
cap = None
frame_width, frame_height = 640, 360
line_x = frame_width // 2
COUNT_LINE = [line_x, 0, line_x, frame_height]

while True:
    current_day = datetime.now(TIMEZONE).date()
    if current_day != last_checked_day:
        print(f"[📆 DEBUG] New day detected: {current_day}")
        last_checked_day = current_day

    if not is_daytime():
        print(f"[🌙] Entering sleep mode at {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")
        if cap:
            print("[🛑 DEBUG] Releasing video capture for sleep...")
            cap.release()
            cap = None
        cv2.destroyAllWindows()
        shutdown_display()
        time.sleep(300)
        continue

    if cap is None:
        print(f"[🔁 DEBUG] Reinitializing camera at {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")
        wake_display()
        cap = setup_capture()

    success, img = cap.read()
    if not success:
        print("[✅] Finished processing video.")
        break

    frame_height, frame_width = img.shape[:2]
    line_x = frame_width // 2
    COUNT_LINE = [line_x, 0, line_x, frame_height]

    imgMasked = cv2.bitwise_and(img, img, mask=mask) if mask is not None else img
    detections = np.empty((0, 5))
    print("[🔍 DEBUG] Running YOLO inference...")
    results = model(imgMasked, stream=True)

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = math.ceil((box.conf[0] * 100)) / 100
            cls = int(box.cls[0])
            currentClass = model.names[cls]
            if currentClass == CLASS_FILTER and conf > CONFIDENCE_THRESHOLD:
                print(f"[📦 DETECTED] {currentClass} at {x1,y1,x2,y2} with {conf}")
                detections = np.vstack((detections, [x1, y1, x2, y2, conf]))

    print(f"[📌 DEBUG] Updating tracker with {len(detections)} detections...")
    resultsTracker = tracker.update(detections)

    for result in resultsTracker:
        x1, y1, x2, y2, id = map(int, result)
        cx, cy = x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2
        center = (cx, cy)

        if id not in id_history:
            id_history[id] = []
        id_history[id].append(center)
        if len(id_history[id]) > 15:
            id_history[id] = id_history[id][-15:]

        if len(id_history[id]) >= 2:
            x_positions = [pt[0] for pt in id_history[id]]
            direction = "Right" if x_positions[-1] > x_positions[0] else "Left"
            crossed = any(
                (x_positions[i] < COUNT_LINE[0] < x_positions[i + 1]) or
                (x_positions[i] > COUNT_LINE[0] > x_positions[i + 1])
                for i in range(len(x_positions) - 1)
            )
            distance = abs(x_positions[-1] - x_positions[0])
            now = time.time()
            recent = last_count_time.get(id, 0)
            if crossed and distance > 15 and (now - recent) > COOLDOWN_SECONDS:
                print(f"[✅ COUNT] Boat ID {id} going {direction}, dist={distance}, time={now}")
                counted_ids.add(id)
                last_count_time[id] = now
                totalCount.append(id)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"boat_{timestamp}.jpg"
                filepath = os.path.join(SNAPSHOT_DIR, filename)
                cv2.imwrite(filepath, img)
                if sheet:
                    try:
                        sheet.append_row([
                            datetime.now().strftime('%Y-%m-%d'),
                            datetime.now().strftime('%H:%M:%S'),
                            len(totalCount),
                            filename,
                            direction
                        ])
                        print("[📊 LOGGED] Added entry to Google Sheet")
                    except Exception as e:
                        print(f"[❌ ERROR] Google Sheets write failed: {e}")

        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 2)
        cv2.putText(img, f"ID: {id} {direction}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
        cv2.circle(img, (cx, cy), 5, (0, 255, 255), -1)
        for pt in id_history[id]:
            cv2.circle(img, pt, 2, (0, 255, 255), -1)

    cv2.line(img, (COUNT_LINE[0], COUNT_LINE[1]), (COUNT_LINE[2], COUNT_LINE[3]), (0, 0, 255), 2)
    cv2.putText(img, f"Total: {len(totalCount)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(img, "Press Q to quit", (img.shape[1] - cv2.getTextSize("Press Q to quit", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0] - 20, img.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow("Boat Detection Test", img)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        print("[👋 DEBUG] Q key pressed — exiting...")
        break

if cap:
    print("[🎬 DEBUG] Releasing video capture...")
    cap.release()
cv2.destroyAllWindows()
print(f"[🏁 DONE] Final boat count: {len(totalCount)}")
