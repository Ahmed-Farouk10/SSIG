import cv2
from ultralytics import YOLO
import numpy as np
from datetime import datetime
import time
import argparse
import sys
import paho.mqtt.client as mqtt
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
MODEL_PATHS = ['yolo8s.pt', 'yolo8n.pt', 'yolov8x.pt']
ALL_PPE_CLASSES = ['face-guard', 'ear-mufs', 'safety-vest', 'gloves', 'glasses']
EXCLUDED_CLASSES = ['hands', 'head', 'face', 'ear', 'tools', 'foot', 'medical-suit', 'safety-suit', 'face-mask-medical']

# MQTT config (set these as environment variables or hardcode for testing)
BROKER = os.getenv("MQTT_BROKER")
PORT = os.getenv("MQTT_PORT")
TOPIC = os.getenv("MQTT_TOPIC", "alerts")
CLIENT_ID = "serbot_inference"
USERNAME = os.getenv("MQTT_USERNAME")
PASSWORD = os.getenv("MQTT_PASSWORD")

# Print MQTT config for debugging
print("BROKER:", BROKER)
print("PORT:", PORT)
print("USERNAME:", USERNAME)
print("PASSWORD:", PASSWORD)

# Validate required variables
missing_vars = []
if not BROKER:
    missing_vars.append('MQTT_BROKER')
if not PORT:
    missing_vars.append('MQTT_PORT')
if not USERNAME:
    missing_vars.append('MQTT_USERNAME')
if not PASSWORD:
    missing_vars.append('MQTT_PASSWORD')
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set them in your .env file or environment before running the script.")
    sys.exit(1)

PORT = int(PORT)

def setup_mqtt():
    # Use MQTTv5 for HiveMQ Cloud, enable TLS
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv5)
    client.tls_set()  # Enable TLS for secure connection
    client.username_pw_set(USERNAME, PASSWORD)
    client.connect(BROKER, PORT)
    client.loop_start()
    return client

def send_alert_mqtt(client, person_box, missing_ppe):
    alert_payload = {
        "icon": "⚠️",
        "title": "CRITICAL: PPE Missing",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": f"Person at {person_box} is missing: {', '.join(missing_ppe)}",
        "priority": "HIGH",
        "type": "critical",
        "person_box": person_box,
        "missing_ppe": missing_ppe
    }
    client.publish(TOPIC, json.dumps(alert_payload))
    print(f"[ALERT] Sent MQTT: {alert_payload}")

def main(conf_threshold=0.5, camera_index=0, required_ppe=None, interval=5):
    print("Loading models...")
    try:
        models = [YOLO(path) for path in MODEL_PATHS]
        print(f"Successfully loaded {len(models)} models.")
    except Exception as e:
        print(f"Error loading models: {e}")
        print(f"Please ensure all model files in {MODEL_PATHS} are present in the directory.")
        sys.exit(1)

    if required_ppe is None:
        required_ppe = ALL_PPE_CLASSES

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print("Could not open webcam.")
        sys.exit(1)

    mqtt_client = setup_mqtt()

    print("Starting inference. Press Ctrl+C to stop.")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame.")
                break

            all_person_boxes = []
            all_person_scores = []
            all_ppe_detections = []

            for model in models:
                results = model(frame, conf=conf_threshold, verbose=False)[0]
                model_class_names = model.names
                
                person_class_indices = [k for k, v in model_class_names.items() if v == 'person']
                if not person_class_indices:
                    continue
                person_class_idx = person_class_indices[0]
                
                ppe_class_indices = [k for k, v in model_class_names.items() if v in ALL_PPE_CLASSES]

                for r in results.boxes:
                    class_id = int(r.cls[0])
                    box = r.xyxy[0].cpu().numpy()
                    
                    if class_id == person_class_idx:
                        all_person_boxes.append(list(box.astype(int)))
                        all_person_scores.append(float(r.conf[0]))
                    elif class_id in ppe_class_indices:
                        all_ppe_detections.append({
                            'class_name': model_class_names[class_id],
                            'xyxy': box.astype(int)
                        })

            # Use Non-Maximum Suppression (NMS) to merge overlapping person boxes
            person_boxes_xywh = [[x1, y1, x2 - x1, y2 - y1] for x1, y1, x2, y2 in all_person_boxes]
            unique_person_indices = []
            if all_person_boxes:
                unique_person_indices = cv2.dnn.NMSBoxes(person_boxes_xywh, all_person_scores, conf_threshold, 0.45)
                if isinstance(unique_person_indices, np.ndarray):
                    unique_person_indices = unique_person_indices.flatten()
            
            final_person_boxes = [all_person_boxes[i] for i in unique_person_indices]

            for person_box in final_person_boxes:
                px1, py1, px2, py2 = person_box
                ppe_found = set()
                for d in all_ppe_detections:
                    x1, y1, x2, y2 = d['xyxy']
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    if px1 <= cx <= px2 and py1 <= cy <= py2:
                        ppe_found.add(d['class_name'])
                
                missing_ppe = [ppe for ppe in required_ppe if ppe not in ppe_found]
                if missing_ppe:
                    send_alert_mqtt(mqtt_client, f"[{px1},{py1},{px2},{py2}]", missing_ppe)
                else:
                    print(f"[{datetime.now()}] Person at [{px1},{py1},{px2},{py2}] - All PPE present.")

            time.sleep(interval)  # Wait before next detection

    except KeyboardInterrupt:
        print("Stopping inference.")
    finally:
        cap.release()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PPE Detection CLI")
    parser.add_argument('--conf', type=float, default=0.5, help='Confidence threshold')
    parser.add_argument('--camera', type=int, default=0, help='Camera index')
    parser.add_argument('--ppe', nargs='*', default=ALL_PPE_CLASSES, help='Required PPE items')
    parser.add_argument('--interval', type=int, default=5, help='Detection interval in seconds')
    args = parser.parse_args()
    main(conf_threshold=args.conf, camera_index=args.camera, required_ppe=args.ppe, interval=args.interval)