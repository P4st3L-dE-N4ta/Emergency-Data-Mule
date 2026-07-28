"""
===============================================================================
Project      : Emergency Data Mule
Module       : YOLO Person Detection Prototype
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Lightweight YOLO prototype for testing person detection and simple posture
    estimation from a live camera feed. The script displays bounding boxes and
    classifies each detected person as standing, sitting, or lying down based
    on the detected box aspect ratio.

===============================================================================

System Role
-----------

This script is a simple early-stage perception test used to validate the
person detector and the posture heuristics before they are integrated into the
more advanced edge vision pipeline.

===============================================================================
"""

import cv2
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
# --- YOLO MODEL INITIALIZATION ---
# ==============================================================================
# Load the YOLOv8 Nano model for fast real-time person detection.
model_path = ensure_model_file(
    "yolov8n.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
)
model = YOLO(model_path)

# ==============================================================================
# --- CAMERA SETUP ---
# ==============================================================================
# Probe the camera index used by the Linux device; on many systems this is 0 or 2.
camera_id = 2

# Force the V4L2 backend for Linux-compatible webcam access.
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

# Set a stable resolution for the camera stream.
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    # Run YOLO inference on the current frame and restrict detections to people.
    results = model(frame, classes=0, verbose=False)

    # Draw a bounding box around each detected person and annotate its inferred posture.
    for box in results[0].boxes:
        # Extract the detection box coordinates from the YOLO result.
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        
        # Compute the detection box dimensions so we can infer posture from shape.
        w = x2 - x1
        h = y2 - y1

        # The aspect ratio of the bounding box provides a simple posture heuristic.
        aspect_ratio = w / h

        # ==============================================================================
        # --- SIMPLE POSTURE CLASSIFICATION ---
        # ==============================================================================
        if aspect_ratio > 1.2:
            posture = "LAYING DOWN"
            priority = "CRITICAL PRIORITY"
            color = (0, 0, 255)  # Red (BGR format)
        elif 0.8 <= aspect_ratio <= 1.2:
            posture = "SITTING"
            priority = "MEDIUM PRIORITY"
            color = (0, 255, 255)  # Yellow
        else:
            posture = "STANDING"
            priority = "LOW PRIORITY"
            color = (0, 255, 0)  # Green

        # Draw the bounding box and a text label directly on the frame.
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Draw a compact label background behind the posture text.
        cv2.rectangle(frame, (x1, y1 - 40), (x2, y1), color, -1)
        
        # Render the posture classification on the frame.
        label = f"{posture} - {priority}"
        cv2.putText(frame, label, (x1 + 5, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    # Show the processed frame to the user.
    cv2.imshow('Emergency Reconnaissance UI', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
