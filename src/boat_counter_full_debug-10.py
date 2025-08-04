"""boat_counter_full_debug.py — Raspberry Pi Edition
===================================================
A **complete**, production‑ready boat counter for Raspberry Pi 4/5 that uses
PiCamera2 or any V4L2 webcam, Ultralytics YOLOv8 for detection, and the blazing‑
fast Rust IOU tracker (`ioutrack‑rs`). Includes:

* Rotating file + console logging at DEBUG level
* Sunrise/sunset sleep to save power (Colorado Springs coords)
* Optional ROI mask, HDMI preview, Google Sheets logging
* Robust camera retry logic
* Snapshot saving for each counted boat

Rebuilt end‑to‑end on 15 Jul 2025 by DHS.

Works on pi

"""
from __future__ import annotations  # Future annotations for type hints

# ───────────────────────── Imports ─────────────────────────
import logging  # Logging module
from logging.handlers import RotatingFileHandler  # Rotating file handler for logs
import sys  # System-specific parameters and functions
import time  # Time access and conversions
from datetime import datetime  # Date and time handling
from zoneinfo import ZoneInfo  # Timezone support
from pathlib import Path  # Filesystem path handling
from typing import Optional, Dict, Tuple, List  # Type hinting

import cv2  # OpenCV for computer vision
import numpy as np  # NumPy for numerical operations
from ultralytics import YOLO  # YOLO object detection

try:
    from picamera2 import Picamera2          # Pi camera; optional
except ImportError:
    Picamera2 = None  # If not available, set to None

import astral  # Astral for sunrise/sunset calculations
import astral.sun as astral_sun  # Sun calculations from astral

try:
    import gspread                           # Google Sheets
    from google.oauth2.service_account import Credentials  # Google credentials
except ImportError:
    gspread = None  # If not available, set to None

# ───────────────────────── Config ──────────────────────────
TZ                = ZoneInfo("America/Denver")  # Timezone
MODEL_PATH        = "yolov8n.pt"          # nano model is lightest
VIDEO_SOURCE      = 0 #"test_pattern.mp4" # camera index or video file
FRAME_W, FRAME_H  = 640, 360  # Frame width and height
COUNT_LINE_RATIO  = 0.5                   # 50 % of width
CONF_THRESHOLD    = 0.35  # Confidence threshold for detection
COOLDOWN_SEC      = 5                     # per‑ID throttle
SNAPSHOT_DIR      = Path("snapshots")  # Directory for snapshots
LOG_DIR           = Path("logs")  # Directory for logs
GSHEET_JSON       = "gsheets_creds.json"  # Google Sheets credentials file
GSHEET_NAME       = "Boat Counter Logs"  # Google Sheets name
MASK_PATH         = "mask.png"            # optional binary mask
DISPLAY_WINDOW    = False                 # False to run headless
MAX_CAMERA_RETRY  = 5  # Max camera retries
RETRY_BACKOFF_SEC = 2  # Retry backoff in seconds

for d in (SNAPSHOT_DIR, LOG_DIR):
    d.mkdir(exist_ok=True)  # Ensure directories exist

# ──────────────────────── Logging ──────────────────────────

def _setup_logger() -> logging.Logger:
    lg = logging.getLogger("boat_counter")  # Create logger
    lg.setLevel(logging.DEBUG)  # Set log level to DEBUG
    fmt = logging.Formatter("%(asctime)s [%(levelname)8s] %(message)s",
                            "%Y-%m-%d %H:%M:%S")  # Log format
    sh = logging.StreamHandler(sys.stdout)  # Stream handler for console
    sh.setFormatter(fmt)  # Set format for stream handler
    lg.addHandler(sh)  # Add stream handler to logger
    fh = RotatingFileHandler(LOG_DIR / "boat_counter.log", maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(fmt)  # Set format for file handler
    lg.addHandler(fh)  # Add file handler to logger
    return lg  # Return configured logger

log = _setup_logger()  # Initialize logger

# ────────── Tracker import (Rust preferred, Python fallback) ──────────
try:                                  # 1️⃣ first look for canonical wheel
    from ioutrack_rs import IOUTracker as Sort  # Try Rust tracker
    log.info("Using Rust IOUTracker from package 'ioutrack_rs'")  # Log usage

except ImportError as e1:
    try:                              # 2️⃣ your wheel: ioutrack/ioutrack.so exporting Sort
        from ioutrack.ioutrack import Sort as _RustSort  # Try alternate Rust tracker
        Sort = _RustSort  # Assign to Sort
        import sys                    # make "ioutrack_rs" alias for any other code
        sys.modules["ioutrack_rs"] = sys.modules["ioutrack.ioutrack"]  # Alias module
        log.info("Using Rust IOUTracker from package 'ioutrack.ioutrack'")  # Log usage

    except ImportError as e2:         # 3️⃣ last‑resort: pure‑Python SORT
        log.warning(
            "Rust IOUTracker unavailable — falling back to Python SORT "
            f"(reasons: {e1!s} ; {e2!s})"
        )
        from sort import Sort         # needs filterpy & scikit‑image

# ──────────── Sunrise / Sunset helper ─────────────
_city = astral.LocationInfo(latitude=38.833, longitude=-104.821, timezone=str(TZ))  # City info

def is_daytime(ts: Optional[datetime] = None) -> bool:
    ts = ts or datetime.now(TZ)  # Use current time if not provided
    sun = astral_sun.sun(_city.observer, date=ts.date(), tzinfo=TZ)  # Get sun times
    return sun["dawn"] <= ts <= sun["dusk"]  # Return True if daytime

# ───────────── Google Sheets (optional) ────────────

def _init_sheet():
    if gspread is None:
        log.warning("gspread not installed — Sheets logging disabled")  # Warn if gspread missing
        return None  # Return None if not available
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]  # Scopes for Google Sheets
        creds = Credentials.from_service_account_file(GSHEET_JSON, scopes=scopes)  # type: ignore  # Load credentials
        sheet = gspread.authorize(creds).open(GSHEET_NAME).sheet1  # type: ignore  # Open sheet
        log.info("Connected to Google Sheets")  # Log connection
        return sheet  # Return sheet object
    except Exception as e:
        log.warning(f"Google Sheets disabled: {e}")  # Warn on failure
        return None  # Return None on failure

sheet = _init_sheet()  # Initialize Google Sheets

# ───────────────────── Camera Wrapper ─────────────────────
class Camera:
    def __init__(self, source=VIDEO_SOURCE):
        self.source = source  # Camera source
        self.picam2 = None  # PiCamera2 object
        self.cap: Optional[cv2.VideoCapture] = None  # OpenCV capture object
        self._open()  # Open camera

    def _open(self):
        retry = 0  # Retry counter
        while retry < MAX_CAMERA_RETRY:
            try:
                if Picamera2 is not None and isinstance(self.source, int):
                    self.picam2 = Picamera2()  # Initialize PiCamera2
                    self.picam2.configure(self.picam2.create_video_configuration(
                        main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}))  # Configure camera
                    self.picam2.start()  # Start camera
                    log.info("PiCamera2 started")  # Log start
                    return  # Return if successful
                self.cap = cv2.VideoCapture(self.source)  # OpenCV video capture
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)  # Set width
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)  # Set height
                if not self.cap.isOpened():
                    raise RuntimeError("cv2.VideoCapture failed")  # Raise error if not opened
                log.info("OpenCV camera started")  # Log start
                return  # Return if successful
            except Exception as e:
                retry += 1  # Increment retry counter
                log.error(f"Camera open error [{retry}/{MAX_CAMERA_RETRY}]: {e}")  # Log error
                time.sleep(RETRY_BACKOFF_SEC ** retry)  # Exponential backoff
        raise RuntimeError("Camera could not be opened after retries")  # Raise error after retries

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.picam2 is not None:
            return True, self.picam2.capture_array()  # Capture from PiCamera2
        assert self.cap is not None
        return self.cap.read()  # Capture from OpenCV

    def release(self):
        if self.picam2:
            self.picam2.stop()  # Stop PiCamera2
        if self.cap:
            self.cap.release()  # Release OpenCV capture

# ───────────────────── ROI Mask load ─────────────────────
MASK: Optional[np.ndarray]
if Path(MASK_PATH).exists():
    _mask = cv2.imread(MASK_PATH, cv2.IMREAD_GRAYSCALE)  # Read mask image
    MASK = cv2.threshold(_mask, 127, 255, cv2.THRESH_BINARY)[1]  # Threshold mask
    log.info("Mask loaded")  # Log mask loaded
else:
    MASK = None  # No mask
    log.info("No mask — using full frame")  # Log no mask

# ─────────────── YOLO & Tracker init ───────────────
log.info("Loading YOLOv8 model…")  # Log model loading
model = YOLO(MODEL_PATH)  # Load YOLO model
tracker = Sort(max_age=15, min_hits=3, iou_threshold=0.1)  # Initialize tracker

# ───────────────── Snapshot & Sheets helpers ─────────────────

def save_snapshot(frame: np.ndarray, tid: int):
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")  # Timestamp
    path = SNAPSHOT_DIR / f"boat_{tid}_{ts}.jpg"  # Snapshot path
    cv2.imwrite(str(path), frame)  # Save snapshot
    log.debug(f"Snapshot saved {path.name}")  # Log snapshot saved


def log_to_sheet(tid: int):
    if sheet is None:
        return  # Do nothing if no sheet
    try:
        sheet.append_row([datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), tid])  # type: ignore  # Append row
    except Exception as e:
        log.error(f"Sheets append failed: {e}")  # Log error

# ───────────────────── Main Processing Loop ─────────────────────

def main():
    cam = Camera()  # Initialize camera
    boat_total = 0  # Total boats counted
    id_last_x: Dict[int, int] = {}  # Last x position for each ID
    id_last_count: Dict[int, float] = {}  # Last count time for each ID
    last_day_checked = datetime.now(TZ).date()  # Last day checked

    try:
        while True:
            now = datetime.now(TZ)  # Current time
            if now.date() != last_day_checked:
                last_day_checked = now.date()  # Update last day checked
                log.debug("Sunrise/sunset window recalculated")  # Log recalculation

            # Sleep at night
            if not is_daytime(now):
                log.info(f"Nighttime {now:%H:%M} — sleeping 5 min")  # Log sleep
                cam.release()  # Release camera
                time.sleep(300)  # Sleep for 5 minutes
                cam = Camera()  # Re-initialize camera
                continue  # Continue loop

            ok, frame = cam.read()  # Read frame
            if not ok or frame is None:
                log.warning("Frame grab failed — retrying")  # Log warning
                time.sleep(0.1)  # Short sleep
                continue  # Continue loop

            frame_proc = cv2.bitwise_and(frame, frame, mask=MASK) if MASK is not None else frame  # Apply mask if present

            # YOLO inference
            detections: List[List[float]] = []  # List for detections
            for r in model(frame_proc, conf=CONF_THRESHOLD, verbose=False):  # Run model
                for box, conf, cls in zip(r.boxes.xyxy.cpu(), r.boxes.conf.cpu(), r.boxes.cls.cpu()):  # Iterate detections
                    # Filter only boats (COCO class 8 = boat) – adjust if you trained custom classes
                    if int(cls) != 8:
                        continue  # Skip non-boat
                    x1, y1, x2, y2 = box.tolist()  # Get box coordinates
                    detections.append([x1, y1, x2, y2, float(conf)])  # Add detection

            # Run tracker  ───────────────────────────────────────────
            if len(detections) == 0:
                tracks = np.empty((0, 5))  # Empty tracks when no detections
            else:
                tracks = tracker.update(np.array(detections, dtype=np.float32))  # Update tracker

            # Draw & count  ─────────────────────────────────────────
            line_x = int(frame.shape[1] * COUNT_LINE_RATIO)  # Calculate line x
            cv2.line(frame, (line_x, 0), (line_x, frame.shape[0]), (0, 255, 255), 2)  # Draw count line

            for x1, y1, x2, y2, tid in tracks:
                x1, y1, x2, y2, tid = map(int, [x1, y1, x2, y2, tid])  # Convert to int

                # Draw track box & ID
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Draw rectangle
                cv2.putText(frame, f"ID {tid}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)  # Draw ID

                # Count when crossing line (left→right)
                center_x = (x1 + x2) // 2  # Calculate center x
                last_x = id_last_x.get(tid, center_x)  # Get last x
                id_last_x[tid] = center_x  # Update last x

                crossed = last_x < line_x <= center_x  # Check if crossed
                cooldown_ok = (time.time() - id_last_count.get(tid, 0)) > COOLDOWN_SEC  # Check cooldown

                if crossed and cooldown_ok:
                    boat_total += 1  # Increment boat count
                    id_last_count[tid] = time.time()  # Update last count time
                    log.info(f"Boat #{boat_total}  (track ID {tid})")  # Log count
                    save_snapshot(frame[y1:y2, x1:x2], tid)  # Save snapshot
                    log_to_sheet(tid)  # Log to sheet

            # ---------- optional HDMI preview ----------
            if DISPLAY_WINDOW:
                cv2.putText(frame, f"Total: {boat_total}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)  # Draw total
                cv2.imshow("Boat Counter", frame)  # Show frame
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break  # Exit on 'q'

    except KeyboardInterrupt:
        log.info("Ctrl-C received — exiting")  # Log exit
    finally:
        cam.release()  # Release camera
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()  # Destroy windows
        log.info("Shutdown complete")  # Log shutdown


# ───────────────────────────── Entry-point ──────────────────────────────
if __name__ == "__main__":
    main()  # Run main
