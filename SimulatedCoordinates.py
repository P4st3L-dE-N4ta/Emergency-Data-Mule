import serial
import time
import json
import sys

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
# 💻 Change this to match your laptop's USB port!
ARDUINO_PORT = '/dev/ttyACM0'  # e.g., 'COM3' for Windows, '/dev/ttyACM0' for Mac/Linux
ARDUINO_BAUD = 115200

PRIORITY_MAP = {
    "Triangle": "High",
    "Square/Rect": "Medium",
    "Circle": "Low"
}

POSTURE_MAP = {
    "Triangle": "LAYING DOWN",
    "Square/Rect": "STANDING",
    "Circle": "SITTING"
}

# The specific coordinates mapped to your requested timeline
# send_at represents the absolute time (in seconds) since the script started
TEST_TARGETS = [
    {
        "shape": "Triangle", 
        "lat": 38.73783468781833, 
        "lon": -9.13828749327068, 
        "send_at": 10.0
    },
    {
        "shape": "Circle", 
        "lat": 38.737801213097434, 
        "lon": -9.138310292045368, 
        "send_at": 23.0
    },
    {
        "shape": "Square/Rect", 
        "lat": 38.73781062786426, 
        "lon": -9.138411545427072, 
        "send_at": 41.0
    }
]

# ==============================================================================
# --- TIMED SIMULATION ROUTINE ---
# ==============================================================================
def run_timed_simulation():
    print(f"🔌 Attempting to connect to Arduino on {ARDUINO_PORT}...")
    
    try:
        with serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1) as arduino:
            time.sleep(2) # Give Arduino a moment to reset on connection
            print("✅ USB Connected! Starting simulation timeline...\n")
            
            start_time = time.time()
            
            for target in TEST_TARGETS:
                shape = target["shape"]
                scheduled_offset = target["send_at"]
                target_time = start_time + scheduled_offset
                
                print(f"⏳ Waiting to send {shape} at T+{scheduled_offset} seconds...")
                
                # Wait loop: Holds until the target time, while still reading incoming Arduino logs
                while True:
                    current_time = time.time()
                    
                    # Check if it's time to fire the payload
                    if current_time >= target_time:
                        break
                        
                    # Print remaining time on the same line so the terminal looks clean
                    time_left = target_time - current_time
                    sys.stdout.write(f"\r   Time until next transmit: {time_left:.1f}s ")
                    sys.stdout.flush()
                    
                    # Continuously read from Arduino so MQTT feedback isn't blocked
                    if arduino.in_waiting > 0:
                        response = arduino.readline().decode('utf-8', errors='ignore').strip()
                        if response:
                            print(f"\n🤖 [ARDUINO]: {response}")
                            
                    time.sleep(0.1)
                
                # Clear the countdown line
                sys.stdout.write("\r" + " " * 40 + "\r")
                sys.stdout.flush()
                
                # Build the payload
                payload = {
                    "posture": POSTURE_MAP[shape],
                    "priority": PRIORITY_MAP[shape],
                    "latitude": target["lat"],
                    "longitude": target["lon"],
                    "gps_status": "Satellite Lock", 
                    "timestamp": int(time.time())
                }
                
                json_string = json.dumps(payload)
                print(f"🚀 [T+{scheduled_offset}s] Sending {shape} Data:\n   {json_string}")
                
                # Send to Arduino
                arduino.write((json_string + '\n').encode('utf-8'))
                print("-" * 60)
                
            # After sending the final payload (Square), wait a few seconds to catch its MQTT success log
            print("🏁 All packages sent. Waiting 5 seconds to catch final logs...")
            end_wait = time.time() + 5.0
            while time.time() < end_wait:
                if arduino.in_waiting > 0:
                    response = arduino.readline().decode('utf-8', errors='ignore').strip()
                    if response:
                        print(f"🤖 [ARDUINO]: {response}")
                time.sleep(0.1)
                
        print("\n✅ Simulation Complete! Safe to close.")

    except serial.SerialException as e:
        print(f"\n❌ Serial Connection Error: {e}")
        print("Check that your ARDUINO_PORT variable matches your OS device manager.")

if __name__ == "__main__":
    run_timed_simulation()