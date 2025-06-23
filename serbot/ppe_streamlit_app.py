import streamlit as st
import cv2
from ultralytics import YOLO
import numpy as np
from PIL import Image
import threading
import time
import pandas as pd
from datetime import datetime
import io
import base64
import queue

# Path to your trained YOLOv8 model
MODEL_PATH = 'yolov8x.pt'

# List of all PPE classes to check for
ALL_PPE_CLASSES = [
    'face-guard', 'ear-mufs', 'safety-vest', 'gloves', 'glasses'
]

# Classes to exclude from display (can be detected, but ignored in output)
EXCLUDED_CLASSES = ['hands', 'head', 'face', 'ear', 'tools', 'foot', 'medical-suit', 'safety-suit', 'face-mask-medical']

# Shared state
class SharedState:
    def __init__(self):
        self.run_camera = False
        self.video_paused = False
        self.log_lines = []
        self.recent_detections = []
        self.update_queue = queue.Queue()

state = SharedState()

# Streamlit UI setup
st.set_page_config(page_title="PPE Detection System", layout="wide")
st.title("PPE Detection System (DEMO)")

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state['initialized'] = True
    st.session_state['log_lines'] = []
    st.session_state['recent_detections'] = []

# Sidebar: Select required PPE for this session
st.sidebar.header('Session PPE Requirements')
selected_ppe = st.sidebar.multiselect(
    'Select required PPE items:', 
    ALL_PPE_CLASSES, 
    default=ALL_PPE_CLASSES
)

# Live status indicator
status_placeholder = st.empty()

# Confidence threshold slider
conf_threshold = st.slider("Detection Confidence Threshold", 
                          min_value=0.1, 
                          max_value=1.0, 
                          value=0.5, 
                          step=0.01)

# User controls
col1, col2, col3 = st.columns(3)
with col1:
    start_cam = st.button("Start Camera")
with col2:
    pause_cam = st.button("Pause/Resume Video")
with col3:
    clear_log = st.button("Clear Log/Table")
stop_cam = st.button("Stop Camera")

frame_placeholder = st.empty()
log_placeholder = st.empty()

# Table for recent detections
st.subheader("Recent Detections and Alerts")
detection_table_placeholder = st.empty()

# Download report button
download_placeholder = st.empty()

# Load the model
try:
    model = YOLO(MODEL_PATH)
    class_names = model.names
    
    # Find class indices
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

except Exception as e:
    st.error(f"Model loading failed: {str(e)}")
    st.stop()

# Thread-safe logging
def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    state.update_queue.put(('log', f"[{timestamp}] {msg}"))

# Detection table update
def update_detection_table():
    if state.recent_detections:
        df = pd.DataFrame(state.recent_detections)
        detection_table_placeholder.dataframe(df, use_container_width=True)
    else:
        detection_table_placeholder.info("No detections yet.")

def get_csv_report():
    if not state.recent_detections:
        return None
    df = pd.DataFrame(state.recent_detections)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

# Download CSV report button
csv_report = get_csv_report()
if csv_report:
    download_placeholder.download_button(
        label="Download Detection Report (CSV)",
        data=csv_report,
        file_name="ppe_detection_report.csv",
        mime="text/csv"
    )

def camera_loop():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log("Could not open webcam.")
        return
        
    try:
        while state.run_camera:
            if state.video_paused:
                time.sleep(0.1)
                continue
                
            ret, frame = cap.read()
            if not ret:
                log("Failed to capture frame.")
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
                log("Person detected .. starting PPE detection")
                
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
                            
                missing_ppe = [ppe for ppe in selected_ppe if ppe not in ppe_found]
                label = 'Missing: ' + (', '.join(missing_ppe) if missing_ppe else 'None')
                
                # Add detection record
                detection_record = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'person_location': f'[{px1},{py1},{px2},{py2}]',
                    'missing_PPE': ', '.join(missing_ppe) if missing_ppe else 'None',
                    'alert': 'Yes' if missing_ppe else 'No'
                }
                
                state.update_queue.put(('detection', detection_record))
                
                # Draw detection box
                color = (0, 0, 255) if missing_ppe else (0, 255, 0)
                cv2.rectangle(frame, (px1, py1), (px2, py2), color, 2)
                cv2.putText(frame, label, (px1, max(py1 - 10, 20)), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
            # Convert frame for display
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            state.update_queue.put(('frame', frame_pil))
            
            time.sleep(0.03)  # ~30 FPS
            
    finally:
        cap.release()
        state.update_queue.put(('status', 'Camera Stopped'))

# Camera thread management
if start_cam and not state.run_camera:
    state.run_camera = True
    state.video_paused = False
    log("Camera started.")
    status_placeholder.markdown(
        '<span style="color:green;font-weight:bold;">● Camera Running</span>', 
        unsafe_allow_html=True
    )
    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()
    
if stop_cam and state.run_camera:
    state.run_camera = False
    log("Camera stopped.")
    status_placeholder.markdown(
        '<span style="color:red;font-weight:bold;">● Camera Stopped</span>', 
        unsafe_allow_html=True
    )

if pause_cam:
    state.video_paused = not state.get('video_paused', False)
    status_placeholder.markdown(
        f'<span style="color:{"orange" if state.video_paused else "green"};font-weight:bold;">● {"Video Paused" if state.video_paused else "Camera Running"}</span>', 
        unsafe_allow_html=True
    )

if clear_log:
    st.session_state['log_lines'] = []
    st.session_state['recent_detections'] = []
    log("Log cleared.")
    detection_table_placeholder.info("No detections yet.")

# Process queue updates from background thread
while True:
    try:
        msg_type, content = state.update_queue.get_nowait()
        
        if msg_type == 'log':
            st.session_state['log_lines'].append(content)
            if len(st.session_state['log_lines']) > 20:
                st.session_state['log_lines'].pop(0)
                
        elif msg_type == 'detection':
            st.session_state['recent_detections'].append(content)
            if len(st.session_state['recent_detections']) > 50:
                st.session_state['recent_detections'].pop(0)
            update_detection_table()
            
        elif msg_type == 'frame':
            frame_placeholder.image(content, channels="RGB")
            
        elif msg_type == 'status':
            status_placeholder.markdown(content, unsafe_allow_html=True)
            
    except queue.Empty:
        break

# Display logs
if st.session_state['log_lines']:
    log_placeholder.code("\n".join(st.session_state['log_lines']), language="bash")
else:
    log_placeholder.info("No logs yet.")

# Update detection table
update_detection_table()