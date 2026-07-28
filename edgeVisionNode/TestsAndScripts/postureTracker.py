"""
===============================================================================
Project      : Emergency Data Mule
Module       : Pose-Based Posture Tracker
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Experimental posture-tracking prototype that uses YOLO pose estimation to
    infer whether a detected person is standing, sitting, or lying down. The
    script visualizes pose landmarks, assigns track IDs, and triggers a simple
    telemetry event when a tracked person is first seen or after a cooldown.

===============================================================================

System Role
-----------

This script is a perception experiment for the edge vision stack. It focuses
on posture classification from pose keypoints and helps validate whether the
vision layer can reliably distinguish the states needed by the downstream
telemetry and alerting logic.

===============================================================================
"""

import cv2
import time
import urllib.request
from pathlib import Path
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
# --- YOLO POSE MODEL INITIALIZATION ---
# ==============================================================================
print("📷 Loading YOLOv8 Pose Model...")
# Use the YOLO pose model to recover skeletal keypoints for posture analysis.
model_path = ensure_model_file(
    "yolov8n-pose.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n-pose.pt"
)
model = YOLO(model_path)

# Probe a fixed list of camera indices and use the first one that produces a valid frame.
camera_test_order = [2, 1, 0]
cap = None
active_camera_id = None

print("🔍 Searching for an available camera...")
for cam_id in camera_test_order:
    print(f"Testing camera ID {cam_id}...")
    temp_cap = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
    
    # Confirm that the camera device opens successfully and can produce a frame.
    if temp_cap.isOpened():
        success, _ = temp_cap.read()
        if success:
            print(f"✅ Successfully connected to camera ID {cam_id}")
            cap = temp_cap
            active_camera_id = cam_id
            break  # Stop searching once a working camera is found.
        else:
            temp_cap.release()
    else:
        temp_cap.release()

# Stop early if no camera can be opened successfully.
if cap is None:
    print("❌ CRITICAL ERROR: Could not find any working cameras. Exiting...")
    exit()

# Select a resolution depending on whether the detected camera is the built-in webcam or a secondary device.
if cam_id == 0:
    print("🎥 Camera 0 detected. Setting high resolution (720p)...")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
else:
    print("🎥 Secondary camera detected. Setting standard resolution (480p)...")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Report the effective resolution that OpenCV actually applied.
actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
print(f"✅ Camera initialized at: {int(actual_width)}x{int(actual_height)}")

# ==============================================================================
# --- TRACKING MEMORY AND COOLDOWN LOGIC ---
# ==============================================================================
# Track the last time each detected person triggered a posture event.
reported_persons = {}

# Prevent repeated alerts for the same person by enforcing a cooldown period.
COOLDOWN_SECONDS = 30

def analyze_posture(kp):
    """
    Estimate posture from the detected person's skeletal keypoints.

    YOLOv8 pose keypoint indices used here:
    5: left shoulder, 6: right shoulder, 11: left hip, 12: right hip.
    """
    try:
        # If the model cannot see the torso keypoints clearly, return an unknown state.
        if kp[5][0] == 0 or kp[11][0] == 0:
            return "UNKNOWN", "Low", (200, 200, 200)

        # Compute the midpoint of the shoulders and hips from visible keypoints.
        shoulder_x = (kp[5][0] + kp[6][0]) / 2
        shoulder_y = (kp[5][1] + kp[6][1]) / 2
        
        # Calculate the midpoint of the hips
        hip_x = (kp[11][0] + kp[12][0]) / 2
        hip_y = (kp[11][1] + kp[12][1]) / 2
        
        # Measure the torso geometry to distinguish a horizontal body pose from an upright one.
        dx = abs(hip_x - shoulder_x)
        dy = abs(hip_y - shoulder_y)
        
        # A wide horizontal torso is treated as a lying-down posture.
        if dx > dy:
            return "LAYING DOWN", "High", (0, 0, 255)
        # A moderate torso tilt is treated as sitting.
        elif dy > 0 and (dx / dy) > 0.4: 
            return "SITTING", "Medium", (0, 255, 255)
        # Otherwise, the person is considered to be standing.
        else:
            return "STANDING", "Low", (0, 255, 0)
            
    except Exception:
        # Fallback for cases where the skeleton is partially occluded or unstable.
        return "UNKNOWN", "Low", (200, 200, 200)

# ==============================================================================
# --- MAIN TRACKING LOOP ---
# ==============================================================================
while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    # Run YOLO tracking with pose estimation so the same person can retain an ID across frames.
    results = model.track(frame, persist=True, classes=0, verbose=False)

    # Only process the frame if the tracker has produced valid detections and IDs.
    if results[0].boxes is not None and results[0].boxes.id is not None:
        # Extract the detection boxes, IDs, and pose keypoints into NumPy arrays.
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy()
        keypoints_array = results[0].keypoints.xy.cpu().numpy()

        for box, track_id, kp in zip(boxes, track_ids, keypoints_array):
            x1, y1, x2, y2 = map(int, box)
            track_id = int(track_id)

            # 1. Infer posture from the skeleton geometry for this tracked person.
            posture, priority, color = analyze_posture(kp)

            # 2. Apply the cooldown logic so the same person does not trigger repeated events too quickly.
            current_time = time.time()
            should_send_payload = False

            # Trigger an event when the person is first seen or when the cooldown period has elapsed.
            if track_id not in reported_persons:
                should_send_payload = True
            elif (current_time - reported_persons[track_id]) > COOLDOWN_SECONDS:
                should_send_payload = True

            # Emit a lightweight telemetry-style event for debugging and prototype validation.
            if should_send_payload:
                print(f"🚀 [PAYLOAD TRIGGERED] Target ID: {track_id} | Posture: {posture} | Priority: {priority}")
                # Update the tracking memory to suppress duplicate events while the cooldown is active.
                reported_persons[track_id] = current_time

            # 3. Draw the bounding box, keypoints, and label directly on the video frame.
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            # Draw skeleton lines (optional, but looks great for demos!)
            for point in kp:
                px, py = int(point[0]), int(point[1])
                if px != 0 and py != 0:  # Only draw visible keypoints.
                    cv2.circle(frame, (px, py), 4, (255, 255, 255), -1)

            # Add labels
            label = f"ID:{track_id} {posture}"
            cv2.rectangle(frame, (x1, y1 - 30), (x2, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow('Pose & Tracking Test UI', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
