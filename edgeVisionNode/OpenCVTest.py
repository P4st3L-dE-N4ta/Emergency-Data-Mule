import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import urllib.request
import os

# MediaPipe Pose Connections
POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10), 
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19), 
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20), 
    (11, 23), (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28), 
    (27, 29), (28, 30), (29, 31), (30, 32), (27, 31), (28, 32)
]

# 1. Download the model if it doesn't exist
model_path = "/home/ricardolas/Documents/Emergency-Data-Mule/edgeVisionNode/models/pose_landmarker.task"
if not os.path.exists(model_path):
    print("Downloading model...")
    model_url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"
    urllib.request.urlretrieve(model_url, model_path)
    print("Download complete.")

# 2. Configure the options
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    min_pose_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# 3. Open the Video Stream using V4L2 (Linux Backend)
# Se /dev/video0 for a webcam do teu portátil, muda o 0 para 2 ou o número que apareceu no ls -l
camera_id = 2
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

# Forçar a resolução base do recetor
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print(f"Erro: Não foi possível abrir /dev/video{camera_id}.")
    exit()

print("A iniciar o MediaPipe no Ubuntu... Pressiona 'q' para sair.")

# 4. Create the landmarker ONCE outside the loop
with vision.PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        success, img = cap.read()
        if not success:
            print("Falha ao receber frame. O recetor desconectou-se.")
            break

        # Convert the image to RGB for MediaPipe
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

        # Perform detection
        results = landmarker.detect(mp_image)

        # Default Status
        status_text = "NO PERSON DETECTED"
        status_color = (0, 0, 255) # Red in BGR
        
        # Draw landmarks if found
        if results.pose_landmarks:
            status_text = "PERSON DETECTED"
            status_color = (0, 255, 0) # Green in BGR
            
            for pose_landmarks in results.pose_landmarks:
                h, w, _ = img.shape
                
                # Draw the dots
                for landmark in pose_landmarks:
                    x, y = int(landmark.x * w), int(landmark.y * h)
                    cv2.circle(img, (x, y), 5, (0, 255, 0), -1)

                # Draw the connections using our custom map
                for connection in POSE_CONNECTIONS:
                    start_idx, end_idx = connection
                    start = pose_landmarks[start_idx]
                    end = pose_landmarks[end_idx]
                    x1, y1 = int(start.x * w), int(start.y * h)
                    x2, y2 = int(end.x * w), int(end.y * h)
                    cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 2)

        # Draw the Text on the Frame
        cv2.putText(img, status_text, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 3)

        # Display the video
        cv2.imshow('MediaPipe FPV (Press Q to exit)', img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
