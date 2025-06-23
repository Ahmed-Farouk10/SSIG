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
import queue
import sys
import asyncio

# This is a workaround for a bug in Python 3.8+ on Windows
# where asyncio.get_event_loop() can fail in some contexts.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Path to your trained YOLOv8 model
MODEL_PATH = 'yolov8x.pt'

# List of all PPE classes to check for
ALL_PPE_CLASSES = [
    'face-guard', 'ear-mufs', 'safety-vest', 'gloves', 'glasses'
]

# Classes to exclude from display (can be detected, but ignored in output)
EXCLUDED_CLASSES = ['hands', 'head', 'face', 'ear', 'tools', 'foot', 'medical-suit', 'safety-suit', 'face-mask-medical']

# Sidebar: Select required PPE for this session
st.sidebar.header('Session PPE Requirements')
selected_ppe = st.sidebar.multiselect('Select required PPE items:', ALL_PPE_CLASSES, default=ALL_PPE_CLASSES)
st.sidebar.info("Note: Camera must be restarted for changes to take effect.")

# Load the model
@st.cache_resource
def load_yolo_model(path):
    try:
        model = YOLO(path)
        return model
    except Exception as e:
        st.error(f"Error loading YOLO model: {e}")
        return None

model = load_yolo_model(MODEL_PATH)

if model is None:
    st.stop()

class_names = model.names

# Find class indices for person, excluded, and PPE classes
person_class_idx = [k for k, v in class_names.items() if v == 'person'][0]
ppe_class_indices = [k for k, v in class_names.items() if v in ALL_PPE_CLASSES]
excluded_class_indices = [k for k, v in class_names.items() if v in EXCLUDED_CLASSES]

if person_class_idx is None:
    st.error('Class "person" not found in model classes.')
    st.stop()

# Streamlit UI
st.set_page_config(page_title="PPE Detection Streamlit App", layout="wide")
st.title("PPE Detection System (DEMO)")

# Live status indicator
status_placeholder = st.empty()

# Confidence threshold slider
conf_threshold = st.slider("Detection Confidence Threshold", min_value=0.1, max_value=1.0, value=0.5, step=0.01)

# User controls
col1, col2, col3, col4 = st.columns(4)
start_cam = col1.button("Start Camera", use_container_width=True)
stop_cam = col2.button("Stop Camera", use_container_width=True, type="primary")
pause_cam = col3.button("Pause/Resume", use_container_width=True)
clear_log = col4.button("Clear Log/Table", use_container_width=True)

frame_placeholder = st.empty()
log_placeholder = st.empty()

# Table for recent detections
st.subheader("Recent Detections and Alerts")
detection_table_placeholder = st.empty()

# Download report button
download_placeholder = st.empty()

# Shared state for camera thread
if "camera_running" not in st.session_state:
    st.session_state.camera_running = False
    st.session_state.camera_thread = None
    st.session_state.stop_event = threading.Event()
    st.session_state.pause_event = threading.Event()
    st.session_state.data_queue = queue.Queue(maxsize=2)
    st.session_state.log_lines = []
    st.session_state.recent_detections = []
    st.session_state.latest_frame = None

run_camera = st.session_state.camera_running

def log(msg):
    st.session_state.log_lines.append(msg)
    # Keep only last 20 logs
    if len(st.session_state.log_lines) > 20:
        st.session_state.log_lines.pop(0)
    log_placeholder.code("\n".join(st.session_state.log_lines), language="bash")

def update_detection_table():
    if st.session_state.recent_detections:
        df = pd.DataFrame(st.session_state.recent_detections)
        detection_table_placeholder.dataframe(df, use_container_width=True)
    else:
        detection_table_placeholder.info("No detections yet.")

def get_csv_report():
    if not st.session_state.recent_detections:
        return None
    df = pd.DataFrame(st.session_state.recent_detections)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

def get_intersection_area(box1, box2):
    """Calculate the intersection area of two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    # The intersection of two axis-aligned bounding boxes is always an
    # axis-aligned bounding box.
    # If the intersection is valid (width and height are positive),
    # return the area, otherwise return 0
    if x2 > x1 and y2 > y1:
        return (x2 - x1) * (y2 - y1)
    return 0

def camera_worker(q, stop_event, pause_event, conf_threshold, selected_ppe_list):
    """
    This function runs in a background thread. It captures frames, runs
    inference, and puts results in a queue. It is fully decoupled from Streamlit.
    """
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        q.put({"error": "Could not open webcam."})
        return

    last_detection_time = 0
    last_known_boxes = [] # To store boxes and labels from the last detection

    while not stop_event.is_set():
        if pause_event.is_set():
            time.sleep(0.5)
            continue

        ret, frame = cap.read()
        if not ret:
            q.put({"error": "Failed to capture frame."})
            time.sleep(0.5)
            continue

        current_time = time.time()
        new_logs = []
        new_detections = []

        # Run detection only every 30 seconds
        if current_time - last_detection_time > 30:
            last_detection_time = current_time
            last_known_boxes.clear() # Clear old boxes

            results = model(frame, conf=conf_threshold, verbose=False)[0]
            all_detections = [{'class': int(b.cls[0]), 'xyxy': b.xyxy[0].cpu().numpy().astype(int)} for b in results.boxes]
            
            persons = [d for d in all_detections if d['class'] == person_class_idx]
            ppe_items = [d for d in all_detections if d['class'] in ppe_class_indices]

            if persons:
                new_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Running detection on {len(persons)} person(s)...")

            for person in persons:
                px1, py1, px2, py2 = person['xyxy']
                ppe_found = set()
                
                # Find PPE items associated with this person
                unassigned_ppe_items = []
                for item in ppe_items:
                    ix1, iy1, ix2, iy2 = item['xyxy']
                    item_area = (ix2 - ix1) * (iy2 - iy1)
                    intersection_area = get_intersection_area(person['xyxy'], item['xyxy'])
                    
                    if item_area > 0 and intersection_area / item_area > 0.5:
                        ppe_found.add(class_names[item['class']])
                    else:
                        unassigned_ppe_items.append(item)
                
                ppe_items = unassigned_ppe_items
                
                missing_ppe = [ppe for ppe in selected_ppe_list if ppe not in ppe_found]
                label = 'Missing: ' + (', '.join(missing_ppe) if missing_ppe else 'None')
                color = (0, 0, 255) if missing_ppe else (0, 255, 0)
                
                # Store the box and its info for redrawing
                last_known_boxes.append({'xyxy': person['xyxy'], 'label': label, 'color': color})
                
                alert = bool(missing_ppe)
                if alert:
                    new_logs.append(f"ALERT: Person at [{px1},{py1}] missing {', '.join(missing_ppe)}")
                
                new_detections.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'person_location': f'[{px1},{py1},{px2},{py2}]',
                    'missing_PPE': ', '.join(missing_ppe) if missing_ppe else 'None',
                    'alert': 'Yes' if alert else 'No'
                })

        # Always draw the last known boxes on the current frame
        for box_info in last_known_boxes:
            px1, py1, px2, py2 = box_info['xyxy']
            cv2.rectangle(frame, (px1, py1), (px2, py2), box_info['color'], 2)
            cv2.putText(frame, box_info['label'], (px1, max(py1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_info['color'], 2)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Only put logs and new detection records when a new detection is made
        q_data = {"frame": frame_rgb}
        if new_logs:
            q_data["logs"] = new_logs
        if new_detections:
            q_data["detections"] = new_detections

        try:
            q.put_nowait(q_data)
        except queue.Full:
            pass # Skip frame if UI is lagging

    cap.release()

# Camera thread management
if start_cam and not run_camera:
    st.session_state.camera_running = True
    st.session_state.stop_event.clear()
    st.session_state.pause_event.clear()
    st.session_state.camera_thread = threading.Thread(
        target=camera_worker,
        args=(st.session_state.data_queue, st.session_state.stop_event, st.session_state.pause_event, conf_threshold, selected_ppe),
        daemon=True
    )
    st.session_state.camera_thread.start()
    log("Camera started.")
    status_placeholder.markdown('<span style="color:green;font-weight:bold;">● Camera Running</span>', unsafe_allow_html=True)
if stop_cam and run_camera:
    st.session_state.camera_running = False
    st.session_state.stop_event.set()
    if st.session_state.camera_thread:
        st.session_state.camera_thread.join(timeout=1)
    st.session_state.latest_frame = None
    with st.session_state.data_queue.mutex:
        st.session_state.data_queue.queue.clear()
    st.rerun()
if pause_cam:
    if st.session_state.pause_event.is_set():
        st.session_state.pause_event.clear()
    else:
        st.session_state.pause_event.set()
    st.rerun()
if clear_log:
    st.session_state.log_lines.clear()
    st.session_state.recent_detections.clear()
    st.rerun()

# Download CSV report button
csv_report = get_csv_report()
if csv_report:
    download_placeholder.download_button(
        label="Download Detection Report (CSV)",
        data=csv_report,
        file_name="ppe_detection_report.csv",
        mime="text/csv"
    )

# Main UI Update Loop
if run_camera:
    status_text = "● Paused" if st.session_state.pause_event.is_set() else "● Camera Running"
    status_color = "orange" if st.session_state.pause_event.is_set() else "green"
    status_placeholder.markdown(f'<p style="color:{status_color};font-weight:bold;">{status_text}</p>', unsafe_allow_html=True)
    
    try:
        data = st.session_state.data_queue.get(timeout=1.5)
        
        if "error" in data:
            st.session_state.log_lines.insert(0, f"ERROR: {data['error']}")
            st.session_state.camera_running = False # Stop on error
        
        if "frame" in data:
            st.session_state.latest_frame = data["frame"]
        
        st.session_state.log_lines.extend(data.get("logs", []))
        st.session_state.recent_detections.extend(data.get("detections", []))
        
        # Trim logs and detections
        if len(st.session_state.log_lines) > 20:
            st.session_state.log_lines = st.session_state.log_lines[-20:]
        if len(st.session_state.recent_detections) > 50:
            st.session_state.recent_detections = st.session_state.recent_detections[-50:]

    except queue.Empty:
        if st.session_state.camera_thread and not st.session_state.camera_thread.is_alive():
             st.session_state.camera_running = False
             st.session_state.log_lines.insert(0, "Error: Camera thread stopped unexpectedly.")
             st.rerun()
        pass

else:
    status_placeholder.markdown('<p style="color:red;font-weight:bold;">● Camera Stopped</p>', unsafe_allow_html=True)

# Render UI components
if st.session_state.latest_frame is not None:
    frame_placeholder.image(st.session_state.latest_frame, channels="RGB", use_container_width=True)
else:
    frame_placeholder.info("Camera is off. Click 'Start Camera' to begin.")

log_placeholder.code("\n".join(st.session_state.log_lines), language="log")

if st.session_state.recent_detections:
    df = pd.DataFrame(reversed(st.session_state.recent_detections))
    detection_table_placeholder.dataframe(df, use_container_width=True, height=350)
    
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    download_placeholder.download_button(
        label="Download Report (CSV)",
        data=csv_buffer.getvalue(),
        file_name="ppe_detection_report.csv",
        mime="text/csv",
        use_container_width=True
    )
else:
    detection_table_placeholder.info("No detections recorded yet.")
    download_placeholder.empty()

# Trigger a rerun to create a live-feed effect
if st.session_state.camera_running:
    # A longer sleep time reduces CPU usage and makes the UI more responsive.
    time.sleep(0.1) 
    st.rerun() 