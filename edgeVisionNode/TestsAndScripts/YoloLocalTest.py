"""
===============================================================================
Project      : Emergency Data Mule
Module       : Local YOLO Telemetry Prototype
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Prototype script that combines computer vision and GPS telemetry for the
    emergency data mule. It receives location updates from a phone or external
    device, runs a YOLO object detector on a local camera feed, classifies the
    detected subject's posture, and emits a JSON telemetry payload either to
    an Arduino serial bridge or to the terminal in local test mode.

===============================================================================

System Role
-----------

This script represents the edge-side perception and telemetry generation
layer of the project. It is responsible for turning visual observations into
structured data that can be forwarded downstream to the Arduino gateway and
ultimately to the cloud bridge.

===============================================================================
"""

import cv2
import json
import time
import serial
import threading
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from ultralytics import YOLO


def ensure_model_file(model_name, model_url):
    """Resolve a model file inside the repository's models folder and download it if missing."""
    current_path = Path(__file__).resolve()
    repo_root = current_path.parents[2] if current_path.parent.name == "TestsAndScripts" else current_path.parents[1]

    models_dir = repo_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / model_name
    if not model_path.exists():
        print(f"⬇️ Downloading {model_name} to {model_path}...")
        urllib.request.urlretrieve(model_url, str(model_path))
        print("✅ Download complete.")

    return str(model_path)

# Shared memory for the most recently received GPS coordinates.
latest_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}

# ==============================================================================
# --- THE BACKGROUND SERVER (Catches Phone GPS) ---
# ==============================================================================
class SensorLoggerHandler(BaseHTTPRequestHandler):
    """Receive JSON location payloads from a phone or sensor logger over HTTP."""
    def do_POST(self):
        global latest_gps

        # Read the HTTP body length and fetch the raw bytes sent by the client.
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))

            # The phone or logger may send a wrapped payload with multiple entries;
            # extract the location object if present and update the shared GPS state.
            if "payload" in data:
                for item in data["payload"]:
                    if item.get("name") == "location":
                        vals = item.get("values", {})
                        latest_gps["latitude"] = vals.get("latitude", latest_gps["latitude"])
                        latest_gps["longitude"] = vals.get("longitude", latest_gps["longitude"])
                        latest_gps["altitude"] = vals.get("altitude", latest_gps["altitude"])
        except Exception:
            pass

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    def log_message(self, format, *args):
        pass


def start_server():
    """Launch the background HTTP server that accepts location updates from a phone."""
    server = HTTPServer(('0.0.0.0', 8000), SensorLoggerHandler)
    print("📡 Background GPS Server listening on port 8000...")
    server.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ==============================================================================
# --- SERIAL ARDUINO BRIDGE / TEST MODE INITIALIZATION ---
# ==============================================================================
ARDUINO_PORT = '/dev/ttyACM0'
try:
    arduino = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
    time.sleep(2)
    print("🔌 Connected to Arduino! (Live Mode)")
except Exception as e:
    print(f"⚠️  Arduino not found on {ARDUINO_PORT}.")
    print("🛠️  RUNNING IN LOCAL TEST MODE (Data will be printed, not sent).")
    arduino = None

# ==============================================================================
# --- COMPUTER VISION AND CAMERA SETUP ---
# ==============================================================================
print("📷 Loading YOLOv8 Model...")
model_path = ensure_model_file(
    "yolov8n.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
)
model = YOLO(model_path)

# Use the default built-in webcam; on Linux this may need V4L2 support.
camera_id = 0
cap = cv2.VideoCapture(camera_id)
# Example fallback for Linux systems that require explicit backend selection:
# cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

last_send_time = 0

# ==============================================================================
# --- VISION LOOP: DETECT, CLASSIFY, AND EMIT TELEMETRY ---
# ==============================================================================
while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    results = model(frame, classes=0, verbose=False) 

    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        aspect_ratio = (x2 - x1) / (y2 - y1)

        # Estimate posture from the bounding box aspect ratio.
        if aspect_ratio > 1.2:
            posture, priority, color = "LAYING DOWN", "High", (0, 0, 255)
        elif 0.8 <= aspect_ratio <= 1.2:
            posture, priority, color = "SITTING", "Medium", (0, 255, 255)
        else:
            posture, priority, color = "STANDING", "Low", (0, 255, 0)

        current_time = time.time()
        
        # Emit a new telemetry packet every few seconds to avoid flooding the bridge.
        if current_time - last_send_time > 5.0:
            
            payload = {
                "priority": priority,
                "posture": posture,
                "latitude": latest_gps["latitude"],
                "longitude": latest_gps["longitude"],
                "altitude": latest_gps["altitude"],
                "timestamp": int(time.time()) 
            }
            
            json_string = json.dumps(payload)
            
            # Send the structured payload to the Arduino gateway when available;
            # otherwise print it locally for prototyping and debugging.
            if arduino:
                print(f"🚀 Sending to Arduino: {json_string}")
                arduino.write((json_string + '\n').encode('utf-8'))
            else:
                print("\n" + "="*40)
                print("🛠️  LOCAL TEST MODE - GENERATED PAYLOAD 🛠️")
                print("="*40)
                # Prints nicely formatted JSON to your terminal
                print(json.dumps(payload, indent=4)) 
                print("="*40 + "\n")
                
            last_send_time = current_time

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        cv2.rectangle(frame, (x1, y1 - 40), (x2, y1), color, -1)
        cv2.putText(frame, f"{posture} - {priority}", (x1 + 5, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow('Emergency Reconnaissance UI', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
if arduino: arduino.close()