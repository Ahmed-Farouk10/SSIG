import streamlit as st
import cv2
from ultralytics import YOLO
import numpy as np
from PIL import Image
import time
import pandas as pd
from datetime import datetime
import io
import base64

# Path to your trained YOLOv8 model
MODEL_PATH = "yolov8x.pt"

# List of all PPE classes to check for
ALL_PPE_CLASSES = [
    'face-guard', 'ear-mufs', 'safety-vest', 'gloves', 'glasses'
]

# Classes to exclude from display (can be detected, but ignored in output)
EXCLUDED_CLASSES = ['hands', 'head', 'face', 'ear', 'tools', 'foot', 'medical-suit', 'safety-suit', 'face-mask-medical']

# Sidebar: Select required PPE for this session
st.sidebar.header('Session PPE Requirements')
selected_ppe = st.sidebar.multiselect('Select required PPE items:', ALL_PPE_CLASSES, default=ALL_PPE_CLASSES)

# Load the model
model = YOLO(MODEL_PATH)
class_names = model.names

# Find class indices for person, excluded, and PPE classes
person_class_idx = None
ppe_class_indices = []
excluded_class_indices = []
for idx, name in class_names.items():
    if name == 'person':
        person_class_idx = idx
    if name in ALL_PPE_CLASSES:
        ppe_class_indices.append(idx)
    if name in EXCLUDED_CLASSES:
        excluded_class_indices.append(idx)

if person_class_idx is None:
    st.error('Class "person" not found in model classes.')
    st.stop()

# Streamlit UI
st.set_page_config(page_title="PPE Detection Streamlit App", layout="wide")

# Enable dark theme via config.toml (see instructions below)

st.title("PPE Detection System (DEMO)")

# Placeholders for UI elements in the desired order
frame_placeholder = st.empty()  # Camera video feed (top)
log_placeholder = st.empty()    # Log area (below video)
detection_table_placeholder = st.empty()  # Detection table (below log)
download_placeholder = st.empty()         # Download button (bottom)

# Live status indicator
status_placeholder = st.empty()

# Confidence threshold slider
conf_threshold = st.slider("Detection Confidence Threshold", min_value=0.1, max_value=1.0, value=0.5, step=0.01)

# Shared state for camera
if 'run_camera' not in st.session_state:
    st.session_state['run_camera'] = False
if 'video_paused' not in st.session_state:
    st.session_state['video_paused'] = False

# Log list to display in the app
if 'log_lines' not in st.session_state:
    st.session_state['log_lines'] = []
log_lines = st.session_state['log_lines']

# List to store detection records for table and CSV
if 'recent_detections' not in st.session_state:
    st.session_state['recent_detections'] = []
recent_detections = st.session_state['recent_detections']
MAX_RECENT = 50  # Max number of recent detections to keep

def log(msg):
    log_lines.append(msg)
    # Keep only last 20 logs
    if len(log_lines) > 20:
        log_lines.pop(0)
    log_placeholder.code("\n".join(log_lines), language="bash")

def update_detection_table():
    if recent_detections:
        df = pd.DataFrame(recent_detections)
        detection_table_placeholder.dataframe(df, use_container_width=True)
    else:
        detection_table_placeholder.info("No detections yet.")

def get_csv_report():
    if not recent_detections:
        return None
    df = pd.DataFrame(recent_detections)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

# User controls
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Start Camera"):
        st.session_state['run_camera'] = True
with col2:
    if st.button("Pause/Resume Video"):
        st.session_state['video_paused'] = not st.session_state.get('video_paused', False)
with col3:
    if st.button("Clear Log/Table"):
        log_lines.clear()
        recent_detections.clear()
        log_placeholder.code("", language="bash")
        detection_table_placeholder.info("No detections yet.")
if st.button("Stop Camera"):
    st.session_state['run_camera'] = False

# Camera loop in main thread
if st.session_state['run_camera']:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log("Error: Could not open webcam.")
        st.session_state['run_camera'] = False
    else:
        while st.session_state['run_camera']:
            if st.session_state.get('video_paused', False):
                time.sleep(0.1)
                continue
            ret, frame = cap.read()
            if not ret:
                log("Error: Failed to capture frame.")
                break
            # Run YOLOv8 inference
            results = model(frame, conf=conf_threshold)[0]
            detections = []
            for box in results.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if conf < conf_threshold:
                    continue
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                detections.append({'class': cls, 'conf': conf, 'xyxy': xyxy})
            persons = [d for d in detections if d['class'] == person_class_idx]
            if persons:
                log("person detected .. starting PPE detection")
            for person in persons:
                px1, py1, px2, py2 = person['xyxy']
                ppe_found = set()
                for d in detections:
                    if d['class'] in ppe_class_indices:
                        x1, y1, x2, y2 = d['xyxy']
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        if px1 <= cx <= px2 and py1 <= cy <= py2:
                            ppe_found.add(class_names[d['class']])
                # Use only selected PPE for this session
                missing_ppe = [ppe for ppe in selected_ppe if ppe not in ppe_found]
                label = 'Missing: ' + (', '.join(missing_ppe) if missing_ppe else 'None')
                text_x = px1
                text_y = max(py1 - 10, 20)
                cv2.putText(frame, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255) if missing_ppe else (0,255,0), 2)
                alert = False
                if missing_ppe:
                    log(f"Person at [{px1},{py1},{px2},{py2}] is missing: {', '.join(missing_ppe)}")
                    log("sending alert, please equip all your safety equipment")
                    alert = True
                # Add detection record
                detection_record = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'person_location': f'[{px1},{py1},{px2},{py2}]',
                    'missing_PPE': ', '.join(missing_ppe) if missing_ppe else 'None',
                    'alert': 'Yes' if alert else 'No'
                }
                recent_detections.append(detection_record)
                if len(recent_detections) > MAX_RECENT:
                    recent_detections.pop(0)
                update_detection_table()
            # Convert BGR to RGB for display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_placeholder.image(frame_pil, channels="RGB", use_column_width=True)
            time.sleep(0.03)  # ~30 FPS
        cap.release()
        frame_placeholder.empty()

# Download CSV report button
csv_report = get_csv_report()
if csv_report:
    download_placeholder.download_button(
        label="Download Detection Report (CSV)",
        data=csv_report,
        file_name="ppe_detection_report.csv",
        mime="text/csv"
    ) 