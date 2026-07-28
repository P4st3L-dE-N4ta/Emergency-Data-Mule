#!/usr/bin/env python3
"""
===============================================================================
Project      : Emergency Data Mule
Module       : Edge Vision Telemetry Node
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 3.0
Last Updated  : 28 July 2026

Description:
    Main edge-side vision application for the emergency data mule. It listens
    for location updates from a phone or external logger, runs YOLO pose
    tracking on a camera feed, infers posture from the observed person, and
    transmits structured telemetry payloads to the Arduino gateway for relay
    through the cellular link.

===============================================================================

System Role
-----------

This script is the perception and telemetry generation component of the
project. It bridges the visual detection and downstream communication layers
by converting observed detections into actionable JSON messages.

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

# ==============================================================================
# --- THE BACKGROUND SERVER (Catches Phone GPS via HTTP PUSH) ---
# ==============================================================================
latest_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}

class SensorLoggerHandler(BaseHTTPRequestHandler):
    """Accept HTTP POST updates from a phone or sensor logger and cache the latest GPS location."""

    def do_POST(self):
        global latest_gps

        # Read the HTTP body length and the payload bytes sent by the client.
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))

            # A wrapped payload may contain several entries; extract the location object if present.
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
    """Run the background HTTP listener that accepts GPS updates from a nearby device."""
    server = HTTPServer(('0.0.0.0', 8000), SensorLoggerHandler)
    print("📡 Background GPS Server listening on port 8000...")
    server.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ==============================================================================
# --- ARDUINO SERIAL BRIDGE INITIALIZATION ---
# ==============================================================================
ARDUINO_PORT = '/dev/ttyACM0'
try:
    arduino = serial.Serial(ARDUINO_PORT, 115200, timeout=1)
    print("🔌 Connected to Arduino USB! Waiting for Cellular/MQTT connection...")
    
    is_ready = False
    while not is_ready:
        if arduino.in_waiting > 0:
            msg = arduino.readline().decode('utf-8', errors='ignore').strip()
            print(f"🤖 Arduino boot logs: {msg}")
            if msg == "READY":
                is_ready = True
                print("✅ Arduino is connected to MQTT. Starting Camera...")

except Exception as e:
    print(f"⚠️ Warning: Could not connect to Arduino: {e}")
    arduino = None

# ==============================================================================
# --- SETUP YOLOv8 POSE MODEL AND MULTI-CAMERA FALLBACK ---
# ==============================================================================
print("📷 Loading YOLOv8 Pose Model...")
model_path = ensure_model_file(
    "yolov8n-pose.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n-pose.pt"
)
model = YOLO(model_path)

camera_test_order = [2, 1, 0]
cap = None

print("🔍 Searching for an available camera...")
for cam_id in camera_test_order:
    temp_cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
    if temp_cap.isOpened():
        success, _ = temp_cap.read()
        if success:
            print(f"✅ Successfully connected to camera ID {cam_id}")
            cap = temp_cap
            
            # Dynamic Resolution based on camera type
            if cam_id == 0:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            else:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            break
        else:
            temp_cap.release()
    else:
        temp_cap.release()

if cap is None:
    print("❌ CRITICAL ERROR: Could not find any working cameras. Exiting...")
    exit()

# ==============================================================================
# --- TRACKING MEMORY AND POSTURE CLASSIFICATION ---
# ==============================================================================
reported_persons = {}
COOLDOWN_SECONDS = 30  # Prevent repeated alerts for the same tracked person too quickly.

def analyze_posture(kp, box):
    try:
        x1, y1, x2, y2 = box
        box_width = x2 - x1
        box_height = y2 - y1
        aspect_ratio = box_width / box_height if box_height > 0 else 0

        # 1. Bounding box aspect ratio is a strong cue for a person lying down.
        if aspect_ratio > 1.5:
            return "LAYING DOWN", "High", (0, 0, 255)

        # 2. Pose keypoints provide a secondary cue based on torso tilt.
        if kp[5][0] != 0 and kp[11][0] != 0:
            shoulder_x = (kp[5][0] + kp[6][0]) / 2
            shoulder_y = (kp[5][1] + kp[6][1]) / 2
            hip_x = (kp[11][0] + kp[12][0]) / 2
            hip_y = (kp[11][1] + kp[12][1]) / 2
            
            dx = abs(hip_x - shoulder_x)
            dy = abs(hip_y - shoulder_y)
            
            if dy > 0:
                torso_ratio = dx / dy
                if torso_ratio > 1.5:
                    return "LAYING DOWN", "High", (0, 0, 255)
                elif torso_ratio > 0.5: 
                    return "SITTING", "Medium", (0, 255, 255)

        # 3. Fallback logic distinguishes sitting from standing when the pose is less clear.
        if 0.65 < aspect_ratio <= 1.5:
            return "SITTING", "Medium", (0, 255, 255)
        else:
            return "STANDING", "Low", (0, 255, 0)
            
    except Exception:
        return "UNKNOWN", "Low", (200, 200, 200)

# ==============================================================================
# --- MAIN PERCEPTION LOOP ---
# ==============================================================================
while cap.isOpened():
    # Listen for messages from the Arduino bridge and print them for debugging.
    if arduino and arduino.in_waiting > 0:
        arduino_response = arduino.readline().decode('utf-8', errors='ignore').strip()
        if arduino_response:
            print(f"🤖 Arduino says: {arduino_response}")

    success, frame = cap.read()
    if not success: break
    
    # --- ROTATE CAMERA 2 ---
    # Rotate 90 degrees to the left (counter-clockwise) if using camera ID 2
    if cam_id == 2:
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # Run YOLOv8 TRACKING with Pose Estimation
    results = model.track(frame, persist=True, classes=0, verbose=False)

    if results[0].boxes is not None and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy()
        keypoints_array = results[0].keypoints.xy.cpu().numpy()

        for box, track_id, kp in zip(boxes, track_ids, keypoints_array):
            x1, y1, x2, y2 = map(int, box)
            track_id = int(track_id)

            # Determine Posture
            posture, priority, color = analyze_posture(kp, box)

            # Ping Logic (ID-based cooldown)
            current_time = time.time()
            should_send_payload = False

            if track_id not in reported_persons:
                should_send_payload = True
            elif (current_time - reported_persons[track_id]) > COOLDOWN_SECONDS:
                should_send_payload = True

            # Transmission
            if should_send_payload:
                payload = {
                    "target_id": track_id,
                    "priority": priority,
                    "posture": posture,
                    "latitude": latest_gps["latitude"],
                    "longitude": latest_gps["longitude"],
                    "altitude": latest_gps["altitude"],
                    "timestamp": int(time.time()) 
                }
                
                json_string = json.dumps(payload)
                print(f"🚀 [PAYLOAD SENT] Target ID: {track_id} | {json_string}")
                
                if arduino:
                    arduino.write((json_string + '\n').encode('utf-8'))
                    
                reported_persons[track_id] = current_time

            # Draw the UI
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            for point in kp:
                px, py = int(point[0]), int(point[1])
                if px != 0 and py != 0:
                    cv2.circle(frame, (px, py), 4, (255, 255, 255), -1)

            label = f"ID:{track_id} {posture}"
            cv2.rectangle(frame, (x1, y1 - 30), (x2, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow('Emergency Reconnaissance UI', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
if arduino: arduino.close()
