import cv2
import threading
import numpy as np
import time
import serial
import pynmea2
import json
from smbus2 import SMBus
import lgpio

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================

# Vision Config
CAMERA_ID = 0          # Keep 1 as defined for your Skyroid receiver
SHOW_VIDEO = False      # Set to False when deploying headless on the tank
REQUIRED_VISIBLE_TIME = 1.0  # Seconds to lock onto a shape
FORGET_TIME = 2.0            # Seconds before treating a lost shape as "new"

# GPS Config
SIMULATE_GPS = False    # Set to False when you connect the real G-Mouse
GPS_PORT = '/dev/ttyACM0'
GPS_BAUD = 9600

# Arduino MKR NB 1500 Config
#ARDUINO_PORT = '/dev/ttyACM1'
ARDUINO_PORT = '/dev/serial0'  # Changed from /dev/ttyACM0
ARDUINO_BAUD = 115200

# Motor & I2C Configuration
I2C_ADDR = 0x34
MOTOR_FIXED_SPEED_ADDR = 0x33
MOTOR_TYPE_ADDR = 0x14
MOTOR_ENCODER_POLARITY_ADDR = 0x15
MOTOR_TYPE_JGB37_520_12V_110RPM = 3

# RC Input GPIO Pins
LGPIO_CHIP = 0
THROTTLE_PIN = 17
STEERING_PIN = 27

# Priority Mapping
PRIORITY_MAP = {
    "Triangle": "High",
    "Square/Rect": "Medium",
    "Circle": "Low"
}
\
# Posture Mapping
POSTURE_MAP = {
    "Triangle": "LAYING DOWN",
    "Square/Rect": "STANDING",
    "Circle": "SITTING"
}

# ==============================================================================
# --- GLOBAL STATE VARIABLES ---
# ==============================================================================
shapes_to_transmit = [] # Queue for shapes that have passed the 1-second lock-on
latest_gps_data = {"lat": 0.0, "lon": 0.0, "status": "No Fix"}
running = True

# RC Pulse Width Dictionary (Shared between lgpio callback and Motor Thread)
pulse_widths = {
    THROTTLE_PIN: 1500,
    STEERING_PIN: 1500
}
rise_ticks = {}

# ==============================================================================
# --- MOTOR UTILITY & CALLBACK FUNCTIONS ---
# ==============================================================================
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def constrain(x, minimum, maximum):
    return max(minimum, min(maximum, x))

def signed_to_byte(value):
    return value & 0xFF

def pwm_callback(chip, gpio, level, tick):
    """Asynchronous edge-detection callback for RC Receiver signals"""
    if level == 1:
        rise_ticks[gpio] = tick
    elif level == 0:
        if gpio in rise_ticks:
            # Convert nanosecond ticks to microseconds
            width = int((tick - rise_ticks[gpio]) / 1000)
            if 700 <= width <= 2100:
                pulse_widths[gpio] = width

# ==============================================================================
# --- THREAD 1: VISION PROCESSING ---
# ==============================================================================
# HSV COLOR + GEOMETRIC VISION PROCESSING
def vision_thread_function():
    global latest_detected_shapes, running
    
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_V4L2) # Change to cv2.CAP_DSHOW if on Windows
    # Lower resolution if needed 
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"[VISION] Error: Could not open /dev/video{CAMERA_ID}.")
        running = False
        return

    print("[VISION] Advanced Vision Thread Started: Active Anti-False-Positive Filters...")

    # Trackers for object state memory
    trackers = {
        "Triangle": {"first_seen": 0.0, "last_seen": 0.0, "reported": False},
        "Square/Rect": {"first_seen": 0.0, "last_seen": 0.0, "reported": False},
        "Circle": {"first_seen": 0.0, "last_seen": 0.0, "reported": False}
    }

    while running and cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        # If using camera ID 2 and it's mounted sideways on the tank, rotate it
        if CAMERA_ID == 2:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # 1. Preprocessing: Smooth the frame and convert to HSV Color Space
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        
        # 2. Define HSV Color Boundaries 
        # (Note: OpenCV Hue ranges from 0-180. Red wraps around the 0/180 line, requiring 2 ranges)
        # TIGHTENED RED BOUNDARIES (Anti-skin tone)
        lower_red1, upper_red1 = np.array([0, 130, 60]), np.array([10, 255, 255])
        lower_red2, upper_red2 = np.array([170, 130, 60]), np.array([180, 255, 255])
        mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        
        # Green channel range
        lower_green, upper_green = (35, 70, 50), (85, 255, 255)
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # Blue channel range
        lower_blue, upper_blue = (90, 70, 50), (130, 255, 255)
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

        # 3. Clean up the masks using Morphological Closing (fills tiny holes inside the colored papers)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_CLOSE, kernel)
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)

        current_shapes = []

        # --- DETECT RED TRIANGLES ---
        contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_red:
            area = cv2.contourArea(c)
            if 800 < area < 50000:
                # Solidity check to filter out open hands
                hull = cv2.convexHull(c)
                hull_area = cv2.contourArea(hull)
                solidity = float(area) / hull_area if hull_area > 0 else 0

                if solidity >= 0.90:
                    epsilon = 0.04 * cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, epsilon, True)
                    # If it's a distinct RED object with exactly 3 corners -> Triangle
                    if len(approx) == 3:
                        current_shapes.append("Triangle")
                        if SHOW_VIDEO:
                            x, y = approx.ravel()[0], approx.ravel()[1]
                            cv2.drawContours(frame, [approx], 0, (0, 0, 255), 3) # Draw Red outline
                            cv2.putText(frame, "Red Triangle", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # --- DETECT BLUE SQUARES ---
        contours_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_blue:
            area = cv2.contourArea(c)
            if 800 < area < 50000:
                epsilon = 0.04 * cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, epsilon, True)
                # If it's a distinct BLUE object with exactly 4 corners -> Square/Rect
                if len(approx) == 4:
                    _, _, w, h_box = cv2.boundingRect(approx)
                    aspect_ratio = float(w) / h_box
                    if 0.6 <= aspect_ratio <= 1.5:
                        current_shapes.append("Square/Rect")
                        if SHOW_VIDEO:
                            x, y = approx.ravel()[0], approx.ravel()[1]
                            cv2.drawContours(frame, [approx], 0, (255, 0, 0), 3) # Draw Blue outline
                            cv2.putText(frame, "Blue Square", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # --- DETECT GREEN CIRCLES ---
        contours_green, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_green:
            area = cv2.contourArea(c)
            if 800 < area < 50000:
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    # Circularity math: 1.0 is a perfect circle
                    circularity = 4 * 3.14159 * (area / (perimeter * perimeter))
                    if 0.7 <= circularity <= 1.2:
                        current_shapes.append("Circle")
                        if SHOW_VIDEO:
                            x, y = c[0][0][0], c[0][0][1]
                            cv2.drawContours(frame, [c], 0, (0, 255, 0), 3) # Draw Green outline
                            cv2.putText(frame, "Green Circle", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # --- MEMORY AND TIMING LOGIC ---
        unique_shapes = list(set(current_shapes))
        current_time = time.time()

        for shape in trackers.keys():
            if shape in unique_shapes:
                if trackers[shape]["first_seen"] == 0.0:
                    trackers[shape]["first_seen"] = current_time
                
                trackers[shape]["last_seen"] = current_time
                time_visible = current_time - trackers[shape]["first_seen"]
                
                if not trackers[shape]["reported"]:
                    if time_visible >= REQUIRED_VISIBLE_TIME:
                        # Append to the queue for the Main Thread to pick up!
                        shapes_to_transmit.append(shape)
                        trackers[shape]["reported"] = True
            else:
                if trackers[shape]["last_seen"] > 0.0:
                    if (current_time - trackers[shape]["last_seen"]) > FORGET_TIME:
                        # Reset memory so it can be detected as a new object later
                        trackers[shape]["first_seen"] = 0.0
                        trackers[shape]["last_seen"] = 0.0
                        trackers[shape]["reported"] = False

        if SHOW_VIDEO:
            # Optional: toggle between showing the raw frame or the "thresh" binary view
            # to see exactly what the computer sees.
            cv2.imshow('Emergency Reconnaissance UI', frame)
            # cv2.imshow('What the Pi Sees (Binary)', thresh) # Uncomment to debug thresholds
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break
        else:
            time.sleep(0.01)

        # Limits vision processing to roughly ~10 FPS, freeing up massive CPU
        time.sleep(0.1)

    cap.release()
    cv2.destroyAllWindows()

# ==============================================================================
# --- THREAD 2: GPS INGESTION ---
# ==============================================================================
def gps_thread_function():
    global latest_gps_data, running
    
    print("[GPS] Thread Started...")
    
    # 1. Simulation Mode (For testing without hardware)
    if SIMULATE_GPS:
        print("[GPS] SIMULATION MODE ACTIVE. Generating dummy coordinates.")
        sim_lat, sim_lon = 41.1579, -8.6291 # Dummy coordinates (Porto)
        while running:
            sim_lat += 0.0001 # Simulate slight movement
            latest_gps_data = {"lat": round(sim_lat, 6), "lon": sim_lon, "status": "Simulated Fix"}
            time.sleep(1) # GPS modules typically update at 1Hz
        return

    # 2. Real Hardware Mode
    while running:
        try:
            # Try to open the serial port
            with serial.Serial(GPS_PORT, GPS_BAUD, timeout=1) as ser:
                print(f"[GPS] Connected successfully on {GPS_PORT}")
                
                while running:
                    line = ser.readline().decode('ascii', errors='replace').strip()
                    
                    # We are looking for GPGGA or GPRMC which hold the coordinates
                    if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                        try:
                            msg = pynmea2.parse(line)
                            
                            # Ensure the module actually has a satellite lock
                            if hasattr(msg, 'latitude') and msg.latitude != 0.0:
                                latest_gps_data = {
                                    "lat": round(msg.latitude, 6), 
                                    "lon": round(msg.longitude, 6), 
                                    "status": "3D Fix"
                                }
                            else:
                                latest_gps_data["status"] = "Searching for Satellites..."
                                
                        except pynmea2.ParseError:
                            pass # Ignore corrupted lines, which happen occasionally over serial
                            
        except serial.SerialException:
            # If the GPS is unplugged or the port is wrong, log it and retry in 2 seconds
            latest_gps_data = {"lat": 0.0, "lon": 0.0, "status": "Disconnected / Port Error"}
            time.sleep(2)

# ==============================================================================
# --- THREAD 3: MOTOR CONTROL (RC INPUT + DIFFERENTIAL MIXING + I2C OUT) ---
# ==============================================================================
def motor_thread_function():
    global running
    print("[MOTOR] Thread Started. Accessing lgpio and smbus2 components...")

    # Open GPIO chip and claim pins locally within the execution thread context
    h = lgpio.gpiochip_open(LGPIO_CHIP)
    lgpio.gpio_claim_alert(h, THROTTLE_PIN, lgpio.BOTH_EDGES)
    lgpio.gpio_claim_alert(h, STEERING_PIN, lgpio.BOTH_EDGES)
    lgpio.gpio_set_debounce_micros(h, THROTTLE_PIN, 10)
    lgpio.gpio_set_debounce_micros(h, STEERING_PIN, 10)

    # Bind the edge alerts to the globally accessible callback function
    cb1 = lgpio.callback(h, THROTTLE_PIN, lgpio.BOTH_EDGES, pwm_callback)
    cb2 = lgpio.callback(h, STEERING_PIN, lgpio.BOTH_EDGES, pwm_callback)

    bus = SMBus(1)
    try:
        bus.write_byte_data(I2C_ADDR, MOTOR_TYPE_ADDR, MOTOR_TYPE_JGB37_520_12V_110RPM)
        time.sleep(0.01)
        bus.write_byte_data(I2C_ADDR, MOTOR_ENCODER_POLARITY_ADDR, 0)
        print("[MOTOR] I2C Motor Driver configured successfully.")
    except Exception as e:
        print("[MOTOR] CRITICAL I2C Configuration failure:", e)
        running = False
        return

    # Native 20Hz control loop (Runs decoupled from the main frame processes)
    while running:
        throttle_pwm = pulse_widths[THROTTLE_PIN]
        steering_pwm = pulse_widths[STEERING_PIN]
        
        throttle = map_value(throttle_pwm, 1000, 2000, -50, 50)
        steering = map_value(steering_pwm, 1000, 2000, -30, 30)

        # Deadband to suppress standard structural motor vibration near stick center
        if abs(throttle) < 5:
            throttle = 0
        if abs(steering) < 5:
            steering = 0

        # Differential drive kinematic mixing calculations
        left_motor = throttle + steering
        right_motor = throttle - steering

        left_motor = constrain(left_motor, -50, 50)
        right_motor = constrain(right_motor, -50, 50)

        # Map to an exportable byte array architecture
        motors = [
            signed_to_byte(left_motor),
            signed_to_byte(right_motor),
            signed_to_byte(left_motor),
            signed_to_byte(right_motor)
        ]
        
        try:
            bus.write_i2c_block_data(I2C_ADDR, MOTOR_FIXED_SPEED_ADDR, motors)
        except Exception as e:
            print("\n[MOTOR] I2C Write Exception:", e)

        time.sleep(0.05) # 20Hz update constraint

    # Emergency Fail-safe routine executed upon system runtime closure flag
    print("\n[MOTOR] Loop broken. Zeroing drivetrain for safety...")
    try:
        bus.write_i2c_block_data(I2C_ADDR, MOTOR_FIXED_SPEED_ADDR, [0, 0, 0, 0])
    except:
        pass

    # Release allocated resource hooks cleanly
    cb1.cancel()
    cb2.cancel()
    lgpio.gpiochip_close(h)
    bus.close()
    print("[MOTOR] Resources released. Thread terminated.")


# ==============================================================================
# --- MAIN DATA MULE LOOP ---
# ==============================================================================
if __name__ == "__main__":

    # 1. Initialize Connection to Arduino MKR NB 1500
    arduino = None
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        print("🔌 Connected to Arduino USB! Waiting for Cellular/MQTT connection...")
        
        is_ready = False
        while not is_ready:
            if arduino.in_waiting > 0:
                msg = arduino.readline().decode('utf-8', errors='ignore').strip()
                print(f"🤖 Arduino boot logs: {msg}")
                if msg == "READY":
                    is_ready = True
                    print("✅ Arduino MQTT is active. Initializing Vision & GPS Threads...")
    except Exception as e:
        print(f"⚠️ Warning: Arduino bypass active (Could not connect: {e})")

    # Launch all 3 dedicated background execution processes
    vision_thread = threading.Thread(target=vision_thread_function, daemon=True)
    vision_thread.start()

    gps_thread = threading.Thread(target=gps_thread_function, daemon=True)
    gps_thread.start()

    motor_thread = threading.Thread(target=motor_thread_function, daemon=True)
    motor_thread.start()

    print("Main Data Mule system running. Press Ctrl+C to stop.")

    try:
        while running:
            # 1. Fetch cellular feedback messages
            if arduino and arduino.in_waiting > 0:
                feedback = arduino.readline().decode('utf-8', errors='ignore').strip()
                if feedback:
                    print(f"🤖 Arduino Response: {feedback}")
            
            # 2. Process confirmed shape triggers provided by the vision thread
            while shapes_to_transmit:
                # Pop the oldest verified shape from the queue
                shape = shapes_to_transmit.pop(0) 
                
                if shape in PRIORITY_MAP:
                    current_gps = latest_gps_data
                    payload = {
                        "posture": POSTURE_MAP[shape],
                        "priority": PRIORITY_MAP[shape],
                        "latitude": current_gps["lat"],
                        "longitude": current_gps["lon"],
                        "gps_status": current_gps["status"],
                        "timestamp": int(time.time())
                    }

                    json_string = json.dumps(payload)
                    print(f"🚀 [SERIAL OUT] Sending Packet -> {json_string}")
                    
                    if arduino:
                        arduino.write((json_string + '\n').encode('utf-8'))
            
            
            ## Keep the main loop running fast enough to catch Arduino feedback, 
            # but slow enough to not max out the CPU.
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nShutting down safely...")
        running = False # Flags all loops to exit instantly

        # Join worker operations to conclude execution steps nicely
        vision_thread.join(timeout=1.0)
        gps_thread.join(timeout=1.0)
        motor_thread.join(timeout=1.0)

        if arduino:
            arduino.close()
        print("Goodbye!")