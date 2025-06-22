import sqlite3
import os

# Get the absolute path of the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Define the database path relative to the script's directory
DB_PATH = os.path.join(script_dir, 'alerts.db')

def init_db():
    try:
        # Connect to the database file using the robust path
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create the 'alerts' table if it doesn't already exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                acknowledged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Commit the changes and close the connection
        conn.commit()
        conn.close()
        print(f"Database '{DB_PATH}' initialized successfully.")
        print("Table 'alerts' created or already exists.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == '__main__':
    init_db() 