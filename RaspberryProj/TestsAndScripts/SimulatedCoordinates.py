"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : Arduino Serial Payload Simulator
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Test utility for the emergency data mule system. The script opens a
    serial connection to the Arduino, waits for a predefined timeline of
    simulated victim events, and transmits JSON payloads that mirror the
    structure used by the main control software.

===============================================================================

Program Architecture
--------------------

The software is composed of two main stages:

    1. Timeline Scheduling
        - Waits for each configured event time before sending its payload.

    2. Serial Transmission
        - Streams JSON-formatted telemetry to the connected Arduino device.

===============================================================================
"""

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

# Mapping used to convert detected shapes into the priority values expected by the system.
PRIORITY_MAP = {
    "Triangle": "High",
    "Square/Rect": "Medium",
    "Circle": "Low"
}

# Mapping used to convert detected shapes into posture labels for the telemetry payload.
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
    """Connect to the Arduino and transmit a scheduled sequence of simulated payloads."""
    print(f"🔌 Attempting to connect to Arduino on {ARDUINO_PORT}...")
    
    try:
        with serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1) as arduino:
            # Give the Arduino a moment to reset after the serial connection is established.
            time.sleep(2)
            print("✅ USB Connected! Starting simulation timeline...\n")
            
            start_time = time.time()
            
            for target in TEST_TARGETS:
                shape = target["shape"]
                scheduled_offset = target["send_at"]
                target_time = start_time + scheduled_offset
                
                print(f"⏳ Waiting to send {shape} at T+{scheduled_offset} seconds...")
                
                # Wait until the target time while still reading any incoming Arduino logs.
                while True:
                    current_time = time.time()
                    
                    # Check if it is time to transmit the payload.
                    if current_time >= target_time:
                        break
                        
                    # Print remaining time on the same line so the terminal remains readable.
                    time_left = target_time - current_time
                    sys.stdout.write(f"\r   Time until next transmit: {time_left:.1f}s ")
                    sys.stdout.flush()
                    
                    # Continuously read from Arduino so MQTT feedback is not blocked.
                    if arduino.in_waiting > 0:
                        response = arduino.readline().decode('utf-8', errors='ignore').strip()
                        if response:
                            print(f"\n🤖 [ARDUINO]: {response}")
                            
                    time.sleep(0.1)
                
                # Clear the countdown line before printing the next event.
                sys.stdout.write("\r" + " " * 40 + "\r")
                sys.stdout.flush()
                
                # Build the payload that mirrors the main control software's JSON format.
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
                
                # Send the payload to the Arduino over serial.
                arduino.write((json_string + '\n').encode('utf-8'))
                print("-" * 60)
                
            # After the final payload is sent, wait briefly to capture any MQTT feedback logs.
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