from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import os
from ultralytics import YOLO
import numpy as np
from PIL import Image
import io
import base64
import cv2

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for the frontend

# Get the absolute path of the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Define the database path relative to the script's directory
DATABASE_PATH = os.path.join(script_dir, 'alerts.db')

# Load YOLO model once
MODEL_PATH = os.path.join(script_dir, '../serbot/yolov8x.pt')
ALL_PPE_CLASSES = ['face-guard', 'ear-mufs', 'safety-vest', 'gloves', 'glasses']
EXCLUDED_CLASSES = ['hands', 'head', 'face', 'ear', 'tools', 'foot', 'medical-suit', 'safety-suit', 'face-mask-medical']
model = YOLO(MODEL_PATH)
class_names = model.names
person_class_idx = [k for k, v in class_names.items() if v == 'person'][0]
ppe_class_indices = [k for k, v in class_names.items() if v in ALL_PPE_CLASSES]


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/check-ppe-image', methods=['POST'])
def check_ppe_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    try:
        img = Image.open(file.stream).convert('RGB')
    except Exception as e:
        return jsonify({'error': f'Invalid image file: {str(e)}'}), 400
    img_np = np.array(img)
    results = model(img_np)[0]
    detections = []
    for box in results.boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        xyxy = box.xyxy[0].cpu().numpy().astype(int)
        detections.append({'class': cls, 'conf': conf, 'xyxy': xyxy})
    persons = [d for d in detections if d['class'] == person_class_idx]
    ppe_items = [d for d in detections if d['class'] in ppe_class_indices]
    response = []
    for person in persons:
        px1, py1, px2, py2 = person['xyxy']
        ppe_found = set()
        for d in ppe_items:
            x1, y1, x2, y2 = d['xyxy']
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            if px1 <= cx <= px2 and py1 <= cy <= py2:
                ppe_found.add(class_names[d['class']])
        missing_ppe = [ppe for ppe in ALL_PPE_CLASSES if ppe not in ppe_found]
        response.append({
            'person_box': f'[{px1},{py1},{px2},{py2}]',
            'missing_ppe': missing_ppe
        })
        # Draw box and label
        color = (0, 0, 255) if missing_ppe else (0, 255, 0)
        cv2.rectangle(img_np, (px1, py1), (px2, py2), color, 2)
        label = 'Missing: ' + (', '.join(missing_ppe) if missing_ppe else 'None')
        cv2.putText(img_np, label, (px1, max(py1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    # Encode annotated image
    _, buffer = cv2.imencode('.png', cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
    img_b64 = base64.b64encode(buffer).decode('utf-8')
    return jsonify({
        'detections': response,
        'annotated_image': img_b64
    })

@app.route('/api/log-alert', methods=['POST'])
def log_alert():
    """
    Receives alert data from the frontend and logs it to the database.
    This is called when a user acknowledges an alert.
    """
    try:
        alert_data = request.json
        print(f"Received alert to log: {alert_data}")

        # Basic validation
        if not all(k in alert_data for k in ['id', 'type', 'title']):
            return jsonify({"status": "error", "message": "Missing required alert data"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO alerts (id, type, title, description, priority) VALUES (?, ?, ?, ?, ?)',
            (
                str(alert_data.get('id')),
                alert_data.get('type'),
                alert_data.get('title'),
                alert_data.get('description'),
                alert_data.get('priority')
            )
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Alert logged successfully"}), 201

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500

if __name__ == '__main__':
    # It's recommended to run Flask apps using a proper WSGI server like Gunicorn or Waitress in production,
    # but the development server is fine for testing.
    app.run(port=5001, debug=True) 