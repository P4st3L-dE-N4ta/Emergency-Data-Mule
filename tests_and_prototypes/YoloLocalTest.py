import cv2
import json
import time
import serial
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from ultralytics import YOLO

# --- Global GPS Storage ---
latest_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}

# ==========================================================
# 1. THE BACKGROUND SERVER (Catches Phone GPS)
# ==========================================================
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
            pass 
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    def log_message(self, format, *args):
        pass 

def start_server():
    server = HTTPServer(('0.0.0.0', 8000), SensorLoggerHandler)
    print("📡 Background GPS Server listening on port 8000...")
    server.serve_forever()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ==========================================================
# 2. SETUP ARDUINO (OR LOCAL TEST MODE)
# ==========================================================
ARDUINO_PORT = '/dev/ttyACM0' 
try:
    arduino = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
    time.sleep(2)
    print("🔌 Connected to Arduino! (Live Mode)")
except Exception as e:
    print(f"⚠️  Arduino not found on {ARDUINO_PORT}.")
    print("🛠️  RUNNING IN LOCAL TEST MODE (Data will be printed, not sent).")
    arduino = None

# ==========================================================
# 3. SETUP YOLOv8 & PC CAMERA
# ==========================================================
print("📷 Loading YOLOv8 Model...")
model = YOLO('yolov8n.pt') 

# CHANGED: 0 is usually the default built-in PC webcam
camera_id = 0 
cap = cv2.VideoCapture(camera_id)
# If Linux gives you a warning about the camera, you might need to use:
# cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

last_send_time = 0

while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    results = model(frame, classes=0, verbose=False) 

    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        aspect_ratio = (x2 - x1) / (y2 - y1)

        # Posture Logic
        if aspect_ratio > 1.2:
            posture, priority, color = "LAYING DOWN", "High", (0, 0, 255)
        elif 0.8 <= aspect_ratio <= 1.2:
            posture, priority, color = "SITTING", "Medium", (0, 255, 255)
        else:
            posture, priority, color = "STANDING", "Low", (0, 255, 0)

        current_time = time.time()
        
        # Trigger every 5 seconds
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
            
            # --- LOCAL TESTING PRINT SECTION ---
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