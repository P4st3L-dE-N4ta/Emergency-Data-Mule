"""
===============================================================================
Project      : Emergency Data Mule
Module       : MediaPipe Pose Prototype
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Standalone pose-estimation prototype for the edge vision node. It uses
    MediaPipe's pose landmarker on a local camera feed, draws body landmarks
    and connections, and displays whether a person is detected in the frame.

===============================================================================

System Role
-----------

This script is a vision experimentation tool used to validate pose estimation
capabilities before integrating the results into the broader telemetry flow.
It complements the YOLO-based approaches by providing a different perception
pipeline for comparison and debugging.

===============================================================================
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import urllib.request
from pathlib import Path

# The body-part connection map used to draw a human skeleton on the video feed.
POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10), 
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19), 
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20), 
    (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28), 
    (27, 29), (28, 30), (29, 31), (30, 32), (27, 31), (28, 32)
]

# ==============================================================================
# --- MODEL DOWNLOAD AND INITIALIZATION ---
# ==============================================================================
# Download the MediaPipe pose model if it is not already available locally.
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

model_path = ensure_model_file(
    "pose_landmarker.task",
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"
)

# Configure the pose detector options, including confidence thresholds.
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ==============================================================================
# --- CAMERA SETUP ---
# ==============================================================================
# Use the V4L2 backend on Linux and select the webcam index to probe.
# If the laptop camera is not on /dev/video2, change the value accordingly.
camera_id = 2
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

# Force a moderate frame resolution for consistent processing.
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print(f"Erro: Não foi possível abrir /dev/video{camera_id}.")
    exit()

print("A iniciar o MediaPipe no Ubuntu... Pressiona 'q' para sair.")

# Create the pose landmarker once outside the frame loop to avoid reinitializing it each iteration.
with vision.PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        success, img = cap.read()
        if not success:
            print("Falha ao receber frame. O recetor desconectou-se.")
            break

        # Convert the frame to RGB so MediaPipe can process it correctly.
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

        # Run pose detection on the current frame.
        results = landmarker.detect(mp_image)

        # Default UI status before any pose is detected.
        status_text = "NO PERSON DETECTED"
        status_color = (0, 0, 255) # Red in BGR
        
        # Draw landmarks and their connections when a pose is detected.
        if results.pose_landmarks:
            status_text = "PERSON DETECTED"
            status_color = (0, 255, 0) # Green in BGR
            
            for pose_landmarks in results.pose_landmarks:
                h, w, _ = img.shape
                
                # Draw each landmark as a green point on the frame.
                for landmark in pose_landmarks:
                    x, y = int(landmark.x * w), int(landmark.y * h)
                    cv2.circle(img, (x, y), 5, (0, 255, 0), -1)

                # Draw skeletal connections using the custom pose graph.
                for connection in POSE_CONNECTIONS:
                    start_idx, end_idx = connection
                    start = pose_landmarks[start_idx]
                    end = pose_landmarks[end_idx]
                    x1, y1 = int(start.x * w), int(start.y * h)
                    x2, y2 = int(end.x * w), int(end.y * h)
                    cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 2)

        # Render a simple status overlay on the video stream.
        cv2.putText(img, status_text, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 3)

        # Display the processed frame to the user.
        cv2.imshow('MediaPipe FPV (Press Q to exit)', img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
