"""boat_counter_full_debug.py — Raspberry Pi Edition
===================================================
A **complete**, production‑ready boat counter for Raspberry Pi 4/5 that uses
PiCamera2 or any V4L2 webcam, Ultralytics YOLOv8 for detection, and the blazing‑
fast Rust IOU tracker (`ioutrack‑rs`). Includes:

* Rotating file + console logging at DEBUG level
* Sunrise/sunset sleep to save power (Colorado Springs coords)
* Optional ROI mask, HDMI preview, Google Sheets logging
* Robust camera retry logic
* Snapshot saving for each counted boat

Rebuilt end‑to‑end on 15 Jul 2025 by Amelia (ChatGPT).
"""
from __future__ import annotations

# ───────────────────────── Imports ─────────────────────────
import logging
from logging.handlers import RotatingFileHandler
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional, Dict, Tuple, List

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from picamera2 import Picamera2          # Pi camera; optional
except ImportError:
    Picamera2 = None

import astral
import astral.sun as astral_sun

try:
    import gspread                           # Google Sheets
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None

# ───────────────────────── Config ──────────────────────────
TZ                = ZoneInfo("America/Denver")
MODEL_PATH        = "yolov8n.pt"          # nano model is lightest
VIDEO_SOURCE      = 0                     # camera index or video file
FRAME_W, FRAME_H  = 640, 360
COUNT_LINE_RATIO  = 0.5                   # 50 % of width
CONF_THRESHOLD    = 0.35
COOLDOWN_SEC      = 5                     # per‑ID throttle
SNAPSHOT_DIR      = Path("snapshots")
LOG_DIR           = Path("logs")
GSHEET_JSON       = "gsheets_creds.json"
GSHEET_NAME       = "Boat Counter Logs"
MASK_PATH         = "mask.png"            # optional binary mask
DISPLAY_WINDOW    = False                 # True to view on HDMI
MAX_CAMERA_RETRY  = 5
RETRY_BACKOFF_SEC = 2

# Ensure directories exist before logger setup
for d in (SNAPSHOT_DIR, LOG_DIR):
    d.mkdir(exist_ok=True)

# ───────────────────────── Logger setup ─────────────────────────
def _setup_logger() -> logging.Logger:
    lg = logging.getLogger("boat_counter")
    lg.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)8s] %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    lg.addHandler(sh)
    fh = RotatingFileHandler(LOG_DIR / "boat_counter.log", maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(fmt)
    lg.addHandler(fh)
    return lg

log = _setup_logger()

# ────────── Tracker import (must come AFTER logger) ──────────
try:
    from ioutrack_rs import IOUTracker as Sort
except ImportError:
    log.warning("ioutrack_rs unavailable — falling back to Python SORT")
    from sort import Sort      # requires scikit‑image
  

# ──────────────────────── Logging ──────────────────────────

# ──────────── Sunrise / Sunset helper ─────────────
_city = astral.LocationInfo(latitude=38.833, longitude=-104.821, timezone=str(TZ))

def is_daytime(ts: Optional[datetime] = None) -> bool:
    ts = ts or datetime.now(TZ)
    sun = astral_sun.sun(_city.observer, date=ts.date(), tzinfo=TZ)
    return sun["dawn"] <= ts <= sun["dusk"]

# ───────────── Google Sheets (optional) ────────────

def _init_sheet():
    if gspread is None:
        log.warning("gspread not installed — Sheets logging disabled")
        return None
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GSHEET_JSON, scopes=scopes)  # type: ignore
        sheet = gspread.authorize(creds).open(GSHEET_NAME).sheet1  # type: ignore
        log.info("Connected to Google Sheets")
        return sheet
    except Exception as e:
        log.warning(f"Google Sheets disabled: {e}")
        return None

sheet = _init_sheet()

# ───────────────────── Camera Wrapper ─────────────────────
class Camera:
    def __init__(self, source=VIDEO_SOURCE):
        self.source = source
        self.picam2 = None
        self.cap: Optional[cv2.VideoCapture] = None
        self._open()

    def _open(self):
        retry = 0
        while retry < MAX_CAMERA_RETRY:
            try:
                if Picamera2 is not None and isinstance(self.source, int):
                    self.picam2 = Picamera2()
                    self.picam2.configure(self.picam2.create_video_configuration(
                        main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}))
                    self.picam2.start()
                    log.info("PiCamera2 started")
                    return
                self.cap = cv2.VideoCapture(self.source)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
                if not self.cap.isOpened():
                    raise RuntimeError("cv2.VideoCapture failed")
                log.info("OpenCV camera started")
                return
            except Exception as e:
                retry += 1
                log.error(f"Camera open error [{retry}/{MAX_CAMERA_RETRY}]: {e}")
                time.sleep(RETRY_BACKOFF_SEC ** retry)
        raise RuntimeError("Camera could not be opened after retries")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.picam2 is not None:
            return True, self.picam2.capture_array()
        assert self.cap is not None
        return self.cap.read()

    def release(self):
        if self.picam2:
            self.picam2.stop()
        if self.cap:
            self.cap.release()

# ───────────────────── ROI Mask load ─────────────────────
MASK: Optional[np.ndarray]
if Path(MASK_PATH).exists():
    _mask = cv2.imread(MASK_PATH, cv2.IMREAD_GRAYSCALE)
    MASK = cv2.threshold(_mask, 127, 255, cv2.THRESH_BINARY)[1]
    log.info("Mask loaded")
else:
    MASK = None
    log.info("No mask — using full frame")

# ─────────────── YOLO & Tracker init ───────────────
log.info("Loading YOLOv8 model…")
model = YOLO(MODEL_PATH)
tracker = Sort(max_age=15, min_hits=3, iou_threshold=0.1)

# ───────────────── Snapshot & Sheets helpers ─────────────────

def save_snapshot(frame: np.ndarray, tid: int):
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    path = SNAPSHOT_DIR / f"boat_{tid}_{ts}.jpg"
    cv2.imwrite(str(path), frame)
    log.debug(f"Snapshot saved {path.name}")


def log_to_sheet(tid: int):
    if sheet is None:
        return
    try:
        sheet.append_row([datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), tid])  # type: ignore
    except Exception as e:
        log.error(f"Sheets append failed: {e}")

# ───────────────────── Main Processing Loop ─────────────────────

def main():
    cam = Camera()
    boat_total = 0
    id_last_x: Dict[int, int] = {}
    id_last_count: Dict[int, float] = {}
    last_day_checked = datetime.now(TZ).date()

    try:
        while True:
            now = datetime.now(TZ)
            if now.date() != last_day_checked:
                last_day_checked = now.date()
                log.debug("Sunrise/sunset window recalculated")

            # Sleep at night
            if not is_daytime(now):
                log.info(f"Nighttime {now:%H:%M} — sleeping 5 min")
                cam.release()
                time.sleep(300)
                cam = Camera()
                continue

            ok, frame = cam.read()
            if not ok or frame is None:
                log.warning("Frame grab failed — retrying")
                time.sleep(0.1)
                continue

            frame_proc = cv2.bitwise_and(frame, frame, mask=MASK) if MASK is not None else frame

            # YOLO inference
            detections: List[List[float]] = []
            for r in model(frame_proc, conf=CONF_THRESHOLD, verbose=False):
                for box, conf, cls in zip(r.boxes.xyxy.cpu(), r.boxes.conf.cpu(), r.boxes.cls.cpu()):
                    # Filter only boats (COCO class 8 = boat) – adjust if you trained custom classes
                    if int(cls) != 8:
                        continue
                    x1, y1, x2, y2 = box.tolist()
                    detections.append([x1, y1, x2, y2, float(conf)])

            # Run tracker  ───────────────────────────────────────────
            tracks = tracker.update(np.array(detections, dtype=np.float32))

            # Draw & count  ─────────────────────────────────────────
            line_x = int(frame.shape[1] * COUNT_LINE_RATIO)
            cv2.line(frame, (line_x, 0), (line_x, frame.shape[0]), (0, 255, 255), 2)

            for x1, y1, x2, y2, tid in tracks:
                x1, y1, x2, y2, tid = map(int, [x1, y1, x2, y2, tid])

                # Draw track box & ID
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"ID {tid}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                # Count when crossing line (left→right)
                center_x = (x1 + x2) // 2
                last_x = id_last_x.get(tid, center_x)
                id_last_x[tid] = center_x

                crossed = last_x < line_x <= center_x
                cooldown_ok = (time.time() - id_last_count.get(tid, 0)) > COOLDOWN_SEC

                if crossed and cooldown_ok:
                    boat_total += 1
                    id_last_count[tid] = time.time()
                    log.info(f"Boat #{boat_total}  (track ID {tid})")
                    save_snapshot(frame[y1:y2, x1:x2], tid)
                    log_to_sheet(tid)

            # ---------- optional HDMI preview ----------
            if DISPLAY_WINDOW:
                cv2.putText(frame, f"Total: {boat_total}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                cv2.imshow("Boat Counter", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        log.info("Ctrl-C received — exiting")
    finally:
        cam.release()
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()
        log.info("Shutdown complete")


# ───────────────────────────── Entry-point ──────────────────────────────
if __name__ == "__main__":
    main()
