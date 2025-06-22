import cv2
import json
import time
import os
from dotenv import load_dotenv
import paho.mqtt.client as paho
from paho import mqtt
from ultralytics import YOLO

# Load environment variables from .env file
load_dotenv(dotenv_path='serbot/.env')

# --- Constants ---
# MQTT Configuration
BROKER = os.getenv("MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT"))
USERNAME = os.getenv("MQTT_USERNAME")
PASSWORD = os.getenv("MQTT_PASSWORD")
TOPIC = "alerts"
CLIENT_ID = "serbot_yolo_client"

# YOLO Configuration
MODEL_PATH = 'serbot/yolov8s.pt'
OBSTACLE_CLASSES = ['person']  # We are defining 'person' as a critical obstacle
ALERT_COOLDOWN_SECONDS = 10  # Cooldown to prevent alert spam

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc, properties=None):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        print("SerBot connected successfully to HiveMQ Cloud!")
    else:
        print(f"SerBot failed to connect, return code {rc}\n")

def on_publish(client, userdata, mid, properties=None):
    """Callback for when a message is published."""
    print(f"Published message with mid: {mid}")

# --- Main Application ---
def run_inference():
    # --- Initialize MQTT Client ---
    client = paho.Client(client_id=CLIENT_ID, protocol=paho.MQTTv5)
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    client.username_pw_set(USERNAME, PASSWORD)
    client.connect(BROKER, PORT)
    client.loop_start()

    # --- Initialize YOLO Model ---
    print(f"Loading YOLO model from {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)
    print("YOLO model loaded.")

    # --- Initialize Video Capture ---
    # Using webcam 0. Change to a video file path if needed.
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video stream or file.")
        return

    last_alert_time = 0
    print("Starting inference loop... (Press 'q' to quit)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # --- Run YOLO Inference ---
        results = model(frame)

        obstacle_detected = False
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]

                if class_name in OBSTACLE_CLASSES:
                    obstacle_detected = True
                    # Draw a bounding box for visualization
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, f"OBSTACLE: {class_name}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                    break  # Found an obstacle, no need to check further in this frame
            if obstacle_detected:
                break

        # --- Send Alert if Obstacle Detected ---
        if obstacle_detected:
            current_time = time.time()
            if (current_time - last_alert_time) > ALERT_COOLDOWN_SECONDS:
                print(f"Obstacle detected: '{OBSTACLE_CLASSES[0]}'. Sending alert!")
                alert_payload = {
                    "id": f"obs_{int(current_time)}",
                    "type": "critical",
                    "icon": "⚠️",
                    "title": "CRITICAL: Obstacle Detected",
                    "time": "Just now",
                    "description": f"An obstacle ({OBSTACLE_CLASSES[0]}) was detected in the robot's path. Avoidance maneuver initiated.",
                    "priority": "HIGH"
                }
                client.publish(TOPIC, payload=json.dumps(alert_payload), qos=1)
                last_alert_time = current_time

        # --- Display the Frame ---
        cv2.imshow('SerBot Obstacle Detection', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # --- Cleanup ---
    cap.release()
    cv2.destroyAllWindows()
    client.loop_stop()
    client.disconnect()
    print("Script finished.")

if __name__ == "__main__":
    run_inference()