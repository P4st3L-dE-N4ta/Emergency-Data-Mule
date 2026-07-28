import cv2
from ultralytics import YOLO

# 1. Load the YOLOv8 Nano model (it will auto-download the first time)
# 'yolov8n.pt' is the fastest model, perfect for real-time video
model = YOLO('/home/ricardolas/Documents/Emergency-Data-Mule/edgeVisionNode/models/yolov8n.pt') 

# 2. Open the Video Stream (Adapted for Skydroid on Linux)
camera_id = 2 # Remember to check 'ls -l /dev/video*' in the terminal (usually it's 0 or 2)

# Force the V4L2 Linux backend
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

# Force the analog resolution (CRITICAL for the Skydroid not to crash)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    # 3. Run YOLOv8 inference on the frame
    # classes=0 ensures we ONLY detect 'person', ignoring cars, dogs, etc.
    results = model(frame, classes=0, verbose=False)

    # 4. Loop through the detected people
    for box in results[0].boxes:
        # Get coordinates of the bounding box
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        
        # Calculate width and height of the box
        w = x2 - x1
        h = y2 - y1
        
        # Calculate Aspect Ratio
        aspect_ratio = w / h

        # 5. Posture Logic based on Aspect Ratio
        if aspect_ratio > 1.2:
            posture = "LAYING DOWN"
            priority = "CRITICAL PRIORITY"
            color = (0, 0, 255) # Red (BGR format)
        elif 0.8 <= aspect_ratio <= 1.2:
            posture = "SITTING"
            priority = "MEDIUM PRIORITY"
            color = (0, 255, 255) # Yellow
        else:
            posture = "STANDING"
            priority = "LOW PRIORITY"
            color = (0, 255, 0) # Green

        # 6. Draw the results on the screen
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Draw background rectangle for text
        cv2.rectangle(frame, (x1, y1 - 40), (x2, y1), color, -1)
        
        # Write Text
        label = f"{posture} - {priority}"
        cv2.putText(frame, label, (x1 + 5, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    # Display the final frame
    cv2.imshow('Emergency Reconnaissance UI', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
