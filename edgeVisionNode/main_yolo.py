import cv2
import json
import time
import serial
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from ultralytics import YOLO

# --- Global GPS Storage ---
# This holds the most recent data pushed by the phone. 
latest_gps = {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}

# ==========================================================
# 1. THE BACKGROUND SERVER (Catches Phone GPS via HTTP PUSH)
# ==========================================================
class SensorLoggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global latest_gps
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            # Navigate the JSON structure you provided
            if "payload" in data:
                for item in data["payload"]:
                    if item.get("name") == "location":
                        vals = item.get("values", {})
                        latest_gps["latitude"] = vals.get("latitude", latest_gps["latitude"])
                        latest_gps["longitude"] = vals.get("longitude", latest_gps["longitude"])
                        latest_gps["altitude"] = vals.get("altitude", latest_gps["altitude"])
        except Exception:
            pass # Silently ignore bad data so it doesn't crash the camera
            
        # Tell the phone the data was received
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    def log_message(self, format, *args):
        pass # Hides standard server logs to keep your terminal clean

def start_server():
    # Listens on all interfaces (0.0.0.0) on port 8000
    server = HTTPServer(('0.0.0.0', 8000), SensorLoggerHandler)
    print("📡 Background GPS Server listening on port 8000...")
    server.serve_forever()

# Start the background server on a separate thread
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ==========================================================
# 2. SETUP ARDUINO SERIAL CONNECTION
# ==========================================================
ARDUINO_PORT = '/dev/ttyACM0' 
try:
    arduino = serial.Serial(ARDUINO_PORT, 115200, timeout=1)
    print("🔌 Connected to Arduino USB! Waiting for Cellular/MQTT connection...")
    
    # Wait until Arduino sends the READY signal
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
# 3. SETUP YOLOv8 & CAMERA
# ==========================================================
print("📷 Loading YOLOv8 Model...")
model = YOLO('yolov8n.pt') 

camera_id = 0 # Using your specified camera ID
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

last_send_time = 0

while cap.isOpened():

    # --- LISTEN TO ARDUINO ---
    if arduino and arduino.in_waiting > 0:
        arduino_response = arduino.readline().decode('utf-8', errors='ignore').strip()
        if arduino_response:
            print(f"🤖 Arduino says: {arduino_response}")


    success, frame = cap.read()
    if not success: break

    results = model(frame, classes=0, verbose=False) # class 0 is 'person'

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

        # --- Formulate Payload and Send to Arduino ---
        current_time = time.time()
        
        # Only send data every 5 seconds to avoid flooding the NB-IoT network
        if current_time - last_send_time > 20.0:
            
            # Form the JSON payload using the data caught by the background thread
            payload = {
                "priority": priority,
                "posture": posture,
                "latitude": latest_gps["latitude"],
                "longitude": latest_gps["longitude"],
                "altitude": latest_gps["altitude"],
                "timestamp": int(time.time()) 
            }
            
            # Convert to string and send to Arduino via Serial
            json_string = json.dumps(payload)
            print(f"🚀 Sending to Arduino: {json_string}")
            
            if arduino:
                # The '\n' tells the Arduino when the message finishes
                arduino.write((json_string + '\n').encode('utf-8'))
                
            last_send_time = current_time

        # Draw the results on the screen
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        cv2.rectangle(frame, (x1, y1 - 40), (x2, y1), color, -1)
        cv2.putText(frame, f"{posture} - {priority}", (x1 + 5, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow('Emergency Reconnaissance UI', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
if arduino: arduino.close()
