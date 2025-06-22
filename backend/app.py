from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import os

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for the frontend

# Get the absolute path of the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Define the database path relative to the script's directory
DATABASE_PATH = os.path.join(script_dir, 'alerts.db')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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