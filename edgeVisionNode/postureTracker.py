import cv2
import time
from ultralytics import YOLO

# ==========================================================
# 1. SETUP YOLOv8 POSE MODEL
# ==========================================================
print("📷 Loading YOLOv8 Pose Model...")
# Using the pose model to get skeletal keypoints
model = YOLO('/home/ricardolas/Documents/Emergency-Data-Mule/edgeVisionNode/models/yolov8n-pose.pt') 

# Define the order of cameras to test
camera_test_order = [2, 1, 0]
cap = None
active_camera_id = None

print("🔍 Searching for an available camera...")
for cam_id in camera_test_order:
    print(f"Testing camera ID {cam_id}...")
    temp_cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
    
    # Check if the port opens AND if we can actually read a frame from it
    if temp_cap.isOpened():
        success, _ = temp_cap.read()
        if success:
            print(f"✅ Successfully connected to camera ID {cam_id}")
            cap = temp_cap
            active_camera_id = cam_id
            break # Stop searching once we find a working camera
        else:
            temp_cap.release()
    else:
        temp_cap.release()

# Safety check in case all cameras fail
if cap is None:
    print("❌ CRITICAL ERROR: Could not find any working cameras. Exiting...")
    exit()

# Conditional resolution based on camera_id
if cam_id == 0:
    print("🎥 Camera 0 detected. Setting high resolution (720p)...")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
else:
    print("🎥 Secondary camera detected. Setting standard resolution (480p)...")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Quick check to see what resolution OpenCV actually managed to set
actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
print(f"✅ Camera initialized at: {int(actual_width)}x{int(actual_height)}")

# ==========================================================
# 2. TRACKING MEMORY
# ==========================================================
# Dictionary to store {track_id: last_time_reported}
reported_persons = {}

# How many seconds to wait before we are allowed to send ANOTHER ping for the SAME person
# Set to a high number (e.g., 300 seconds / 5 mins) to only ping once per emergency
COOLDOWN_SECONDS = 30

def analyze_posture(kp):
    """
    Calculates posture based on skeletal keypoints rather than bounding boxes.
    YOLOv8 Pose Keypoint Indices: 
    5: Left Shoulder, 6: Right Shoulder, 11: Left Hip, 12: Right Hip
    """
    try:
        # Prevent errors if the model can't see the person clearly and defaults to (0,0)
        if kp[5][0] == 0 or kp[11][0] == 0:
            return "UNKNOWN", "Low", (200, 200, 200)

        # Calculate the midpoint of the shoulders
        shoulder_x = (kp[5][0] + kp[6][0]) / 2
        shoulder_y = (kp[5][1] + kp[6][1]) / 2
        
        # Calculate the midpoint of the hips
        hip_x = (kp[11][0] + kp[12][0]) / 2
        hip_y = (kp[11][1] + kp[12][1]) / 2
        
        # Calculate the horizontal (dx) and vertical (dy) distance between shoulders and hips
        dx = abs(hip_x - shoulder_x)
        dy = abs(hip_y - shoulder_y)
        
        # If the horizontal distance is greater than the vertical, the torso is sideways (Laying down)
        if dx > dy:
            return "LAYING DOWN", "High", (0, 0, 255)
        # If the torso is slightly tilted, consider it sitting
        elif dy > 0 and (dx / dy) > 0.4: 
            return "SITTING", "Medium", (0, 255, 255)
        # Otherwise, they are upright
        else:
            return "STANDING", "Low", (0, 255, 0)
            
    except Exception:
        # Fallback if the model can't see the shoulders/hips clearly
        return "UNKNOWN", "Low", (200, 200, 200)

# ==========================================================
# 3. MAIN LOOP
# ==========================================================
while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    # Run YOLOv8 TRACKING with Pose Estimation
    #persist=True tells the model to remember IDs across frames
    results = model.track(frame, persist=True, classes=0, verbose=False)

    # Check if any objects are currently being tracked
    if results[0].boxes is not None and results[0].boxes.id is not None:
        # Extract everything into clean Numpy arrays right away
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy()
        keypoints_array = results[0].keypoints.xy.cpu().numpy()

        for box, track_id, kp in zip(boxes, track_ids, keypoints_array):
            x1, y1, x2, y2 = map(int, box)
            track_id = int(track_id)

            # 1. Determine Posture via Skeleton (passing the raw 17x2 array)
            posture, priority, color = analyze_posture(kp)

            # 2. Check Ping/Payload Logic
            current_time = time.time()
            should_send_payload = False

            # If we've never seen this person, OR their cooldown has expired
            if track_id not in reported_persons:
                should_send_payload = True
            elif (current_time - reported_persons[track_id]) > COOLDOWN_SECONDS:
                should_send_payload = True

            # Mock Payload Transmission
            if should_send_payload:
                print(f"🚀 [PAYLOAD TRIGGERED] Target ID: {track_id} | Posture: {posture} | Priority: {priority}")
                # Update the memory so we don't spam this ID again
                reported_persons[track_id] = current_time

            # 3. Draw the UI
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            # Draw skeleton lines (optional, but looks great for demos!)
            for point in kp:
                px, py = int(point[0]), int(point[1])
                if px != 0 and py != 0: # Only draw if the keypoint is visible
                    cv2.circle(frame, (px, py), 4, (255, 255, 255), -1)

            # Add labels
            label = f"ID:{track_id} {posture}"
            cv2.rectangle(frame, (x1, y1 - 30), (x2, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow('Pose & Tracking Test UI', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
