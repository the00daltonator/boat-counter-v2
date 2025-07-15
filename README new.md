
# Boat Counter (Raspberry Pi Edition) – README
**File:** `boat_counter_full_debug-10.py`  
**Last rebuilt:** 15 Jul 2025

---

## 1. What it does
A self‑contained, production‑ready “boat counter” for Raspberry Pi 4/5 (or any Linux box with a webcam). It:

* Detects boats in real time with **YOLOv8**
* Tracks them frame‑to‑frame with the ultra‑fast Rust tracker **`ioutrack‑rs`**
* Counts line‑crossing events and logs each boat to **Google Sheets**
* Sleeps automatically at night (Astral sunrise/sunset) to save power
* Saves snapshots, rotates log files, shows an optional HDMI preview, and survives camera drop‑outs

---

## 2. Hardware you need
| Component | Min spec |
|-----------|----------|
| Raspberry Pi | Pi 4 Model B (2 GB+) or Pi 5 |
| Camera     | Official **PiCamera v3 (IMX708)** *or* any V4L2 USB webcam |
| Storage    | 16 GB+ micro‑SD (Class 10) |
| Optional   | Internet (Wi‑Fi or Ethernet) for Google Sheets logging |

---

## 3. Software prerequisites

```bash
# Python 3.11 or newer
sudo apt update
sudo apt install python3-pip python3-opencv libatlas-base-dev rustc cargo

# Python libs
pip install ultralytics==8.* numpy opencv-python gspread google-auth astral \
            picamera2 ioutrack-rs==0.* pytz zoneinfo
```

> **Tip:** compiling `ioutrack‑rs` the first time may take 2–3 minutes on a Pi 4.

---

## 4. File / folder layout

```
boat-counter/
├─ boat_counter_full_debug-10.py   ← this script
├─ yolov8n.pt                      ← default YOLOv8 nano weights
├─ gsheets_creds.json              ← service‑account key (if using Sheets)
├─ mask.png                        ← optional 1‑bit ROI mask
├─ snapshots/                      ← auto‑saved boat images
└─ logs/                           ← rotating *.log files
```

Create the `snapshots` and `logs` directories once; the script will reuse them.

---

## 5. Key settings (edit at top of the script)

| Constant | Purpose | Default |
|----------|---------|---------|
| `MODEL_PATH` | Path to YOLO weight file | `"yolov8n.pt"` |
| `VIDEO_SOURCE` | `0` = first camera, or path to a video | `0` |
| `COUNT_LINE_RATIO` | Horizontal line position (0 – 1 of frame width) | `0.5` |
| `CONF_THRESHOLD` | YOLO confidence cut‑off | `0.35` |
| `GSHEET_JSON` | Service‑account JSON key | `"gsheets_creds.json"` |
| `GSHEET_NAME` | Spreadsheet title | `"Boat Counter Logs"` |
| `MASK_PATH` | Binary mask file (optional) | `"mask.png"` |
| `DISPLAY_WINDOW` | HDMI preview on/off | `False` |

---

## 6. First‑time setup

1. **Clone / copy** the folder to the Pi.  
2. **Add YOLO weights** (or train and export your own).  
3. **Create a Google Service Account** → share your sheet → download the key as `gsheets_creds.json`.  
4. (Optional) **Draw an ROI mask** in GIMP/Photoshop; white = active, black = ignore.  
5. **Test camera**: `libcamera-hello -t 5000` or `ffplay /dev/video0`.

---

## 7. Run it

```bash
python3 boat_counter_full_debug-10.py
```

You’ll see rotating log output in `logs/boat_counter.log`.  
If `DISPLAY_WINDOW=True`, an HDMI window shows detections and the red counting line.

---

## 8. Autostart on boot (systemd)

```ini
# /etc/systemd/system/boat-counter.service
[Unit]
Description=Boat Counter
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/boat-counter
ExecStart=/usr/bin/python3 /home/pi/boat-counter/boat_counter_full_debug-10.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable boat-counter
sudo systemctl start  boat-counter
```

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `cv2.VideoCapture` fails | Wrong `VIDEO_SOURCE`; check `ls /dev/video*` |
| Blank detections | Bad model path or low lighting; verify `MODEL_PATH` |
| Google Sheets auth error | JSON key not found / sheet not shared with service account |
| “legacy SDN tuning” warnings | Harmless PiCamera2 notice; ignore |

---

## 10. License & credits
Created by **DHS (the00daltonator)** with ♥ and open‑source tools. YOLOv8 by Ultralytics, `ioutrack‑rs` by Moritz Doleschal, and Picamera2 by Raspberry Pi Trading Ltd. Use, modify, and share freely—just keep the credits.
