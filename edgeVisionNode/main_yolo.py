#!/usr/bin/env python3
import cv2
import json
import time
import serial
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from ultralytics import YOLO

# ==========================================================
# 1. THE BACKGROUND SERVER (Catches Phone GPS via HTTP PUSH)
# ==========================================================
latest_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}

class SensorLoggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global latest_gps
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            if "payload" in data:
                for item in data["payload"]:
                    if item.get("name") == "location":
                        vals = item.get("values", {})
                        latest_gps["latitude"] = vals.get("latitude", latest_gps["latitude"])
                        latest_gps["longitude"] = vals.get("longitude", latest_gps["longitude"])
                        latest_gps["altitude"] = vals.get("altitude", latest_gps["altitude"])
        except Exception:
            pass # Silently ignore bad data
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    def log_message(self, format, *args):
        pass # Hides standard server logs

def start_server():
    server = HTTPServer(('0.0.0.0', 8000), SensorLoggerHandler)
    print("📡 Background GPS Server listening on port 8000...")
    server.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ==========================================================
# 2. SETUP ARDUINO SERIAL CONNECTION
# ==========================================================
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

# ==========================================================
# 3. SETUP YOLOv8 POSE MODEL & MULTI-CAMERA FALLBACK
# ==========================================================
print("📷 Loading YOLOv8 Pose Model...")
model = YOLO('/home/ricardo/Documents/Emergency-Data-Mule/edgeVisionNode/models/yolov8n-pose.pt') 

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

# ==========================================================
# 4. TRACKING MEMORY & POSTURE LOGIC
# ==========================================================
reported_persons = {}
COOLDOWN_SECONDS = 30 # Wait 30s before sending ANOTHER alert for the SAME person

def analyze_posture(kp, box):
    try:
        x1, y1, x2, y2 = box
        box_width = x2 - x1
        box_height = y2 - y1
        aspect_ratio = box_width / box_height if box_height > 0 else 0

        # 1. Bounding Box check for LAYING DOWN
        if aspect_ratio > 1.5:
            return "LAYING DOWN", "High", (0, 0, 255)

        # 2. Skeletal Torso Tilt
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

        # 3. Fallback SITTING vs STANDING
        if 0.65 < aspect_ratio <= 1.5:
            return "SITTING", "Medium", (0, 255, 255)
        else:
            return "STANDING", "Low", (0, 255, 0)
            
    except Exception:
        return "UNKNOWN", "Low", (200, 200, 200)

# ==========================================================
# 5. MAIN LOOP
# ==========================================================
while cap.isOpened():
    # --- LISTEN TO ARDUINO ---
    if arduino and arduino.in_waiting > 0:
        arduino_response = arduino.readline().decode('utf-8', errors='ignore').strip()
        if arduino_response:
            print(f"🤖 Arduino says: {arduino_response}")

    success, frame = cap.read()
    if not success: break

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
