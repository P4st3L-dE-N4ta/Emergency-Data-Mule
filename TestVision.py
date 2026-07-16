import cv2
import numpy as np
import time
import json

# --- CONFIGURATION ---
CAMERA_ID = 2  
REQUIRED_VISIBLE_TIME = 1.0    # Seconds a shape must be continuously visible to trigger a payload
FORGET_TIME = 2.0              # Seconds the shape must be out of frame before the robot "forgets" it

def test_vision():
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_V4L2) 
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"Error: Could not open /dev/video{CAMERA_ID}. Try changing CAMERA_ID.")
        return

    print("Vision Test Started! (Anti-False-Positive Mode Active)")
    print("Press 'q' on any video window to quit.\n")

    # --- TRACKING VARIABLES ---
    trackers = {
        "Triangle": {"first_seen": 0.0, "last_seen": 0.0, "reported": False},
        "Square/Rect": {"first_seen": 0.0, "last_seen": 0.0, "reported": False},
        "Circle": {"first_seen": 0.0, "last_seen": 0.0, "reported": False}
    }
    
    PRIORITY_MAP = {"Triangle": "Critical", "Square/Rect": "Medium", "Circle": "Low"}

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        if CAMERA_ID == 2:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        
        # --- FIX 1: TIGHTEN RED BOUNDARIES ---
        # Minimum Saturation raised from 70 to 130 to completely blind the camera to human skin tones
        lower_red1, upper_red1 = np.array([0, 130, 60]), np.array([10, 255, 255])
        lower_red2, upper_red2 = np.array([170, 130, 60]), np.array([180, 255, 255])
        mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        
        # Green and Blue channels remain standard
        lower_green, upper_green = np.array([35, 70, 50]), np.array([85, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        lower_blue, upper_blue = np.array([90, 70, 50]), np.array([130, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_CLOSE, kernel)
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)

        current_shapes = []

        # --- DETECT RED TRIANGLES (WITH SOLIDITY FILTER) ---
        contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_red:
            area = cv2.contourArea(c)
            if 800 < area < 50000:
                
                # --- FIX 2: SOLIDITY VERIFICATION ---
                hull = cv2.convexHull(c)
                hull_area = cv2.contourArea(hull)
                solidity = float(area) / hull_area if hull_area > 0 else 0
                
                # Pure paper triangles have a solidity > 0.90. Organic shapes like hands fail this.
                if solidity < 0.90:
                    continue

                approx = cv2.approxPolyDP(c, 0.04 * cv2.arcLength(c, True), True)
                if len(approx) == 3:
                    current_shapes.append("Triangle")
                    cv2.drawContours(frame, [approx], 0, (0, 0, 255), 3)

        # --- DETECT BLUE SQUARES ---
        contours_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_blue:
            if 800 < cv2.contourArea(c) < 50000:
                approx = cv2.approxPolyDP(c, 0.04 * cv2.arcLength(c, True), True)
                if len(approx) == 4:
                    _, _, w, h_box = cv2.boundingRect(approx)
                    if 0.6 <= float(w) / h_box <= 1.5:
                        current_shapes.append("Square/Rect")
                        cv2.drawContours(frame, [approx], 0, (255, 0, 0), 3)

        # --- DETECT GREEN CIRCLES ---
        contours_green, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours_green:
            area = cv2.contourArea(c)
            if 800 < area < 50000:
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    if 0.7 <= (4 * 3.14159 * (area / (perimeter * perimeter))) <= 1.2:
                        current_shapes.append("Circle")
                        cv2.drawContours(frame, [c], 0, (0, 255, 0), 3)

        unique_shapes = list(set(current_shapes))
        current_time = time.time()
        status_outputs = []

        # --- PERSISTENCE & OBJECT STATE LOGIC ---
        for shape in trackers.keys():
            if shape in unique_shapes:
                if trackers[shape]["first_seen"] == 0.0:
                    trackers[shape]["first_seen"] = current_time
                
                trackers[shape]["last_seen"] = current_time
                time_visible = current_time - trackers[shape]["first_seen"]
                
                if not trackers[shape]["reported"]:
                    if time_visible >= REQUIRED_VISIBLE_TIME:
                        payload = {
                            "shape": shape,
                            "priority": PRIORITY_MAP[shape],
                            "latitude": 41.1579,
                            "longitude": -8.6291,
                            "gps_status": "Simulated Fix",
                            "timestamp": int(current_time)
                        }
                        print(f"\n\n🚀 [SERIAL OUT] Sending Packet -> {json.dumps(payload)}")
                        trackers[shape]["reported"] = True
                    else:
                        status_outputs.append(f"{shape} ({time_visible:.1f}s)")
                else:
                    status_outputs.append(f"{shape} [REPORTED]")
            else:
                if trackers[shape]["last_seen"] > 0.0:
                    time_missing = current_time - trackers[shape]["last_seen"]
                    if time_missing > FORGET_TIME:
                        trackers[shape]["first_seen"] = 0.0
                        trackers[shape]["last_seen"] = 0.0
                        trackers[shape]["reported"] = False
                    else:
                        status_outputs.append(f"Lost {shape}? ({FORGET_TIME - time_missing:.1f}s)")

        if status_outputs:
            output_str = f"Tracking: {', '.join(status_outputs)}"
        else:
            output_str = "Tracking: [ None ]"
            
        print(f"\r{output_str:<80}", end="")
        cv2.imshow('Main Camera View', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n\nExiting Vision Test...")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_vision()