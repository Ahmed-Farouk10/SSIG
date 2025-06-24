import { startParticleSystem } from './animations.js';
import { AlertManager } from './alerts.js';
import { SensorManager } from './sensors.js';

class App {
    constructor() {
        this.isConnected = true;
        this.isDarkMode = import.meta.env.VITE_DEFAULT_THEME === 'dark';
        this.alertManager = new AlertManager();
        this.sensorManager = new SensorManager();
        this.initializeEventListeners();
        
        // Start particle system immediately
        startParticleSystem();
    }

    initializeEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('themeToggle');
        themeToggle.addEventListener('click', () => this.toggleTheme());

        // Connection toggle
        const toggleConnection = document.getElementById('toggleConnection');
        toggleConnection.addEventListener('click', () => this.toggleConnection());

        // Start sensor data updates
        const updateInterval = parseInt(import.meta.env.VITE_SENSOR_UPDATE_INTERVAL) || 5000;
        setInterval(() => this.sensorManager.updateSensorData(), updateInterval);
    }

    toggleTheme() {
        this.isDarkMode = !this.isDarkMode;
        const dashboard = document.getElementById('dashboard');
        const themeToggle = document.getElementById('themeToggle');

        if (this.isDarkMode) {
            dashboard.classList.remove('light-mode');
            themeToggle.textContent = '🌙';
        } else {
            dashboard.classList.add('light-mode');
            themeToggle.textContent = '☀️';
        }
    }

    toggleConnection() {
        this.isConnected = !this.isConnected;
        const statusCard = document.getElementById('statusCard');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');

        if (this.isConnected) {
            statusCard.className = 'status-card connected';
            statusIndicator.className = 'status-indicator connected';
            statusText.textContent = 'Connected to SerBot';
        } else {
            statusCard.className = 'status-card disconnected';
            statusIndicator.className = 'status-indicator disconnected';
            statusText.textContent = 'Disconnected from SerBot';
        }
    }
}

// Initialize the application
const appInstance = new App();

// MQTT Integration for Real-Time Alerts
let firstMqttAlertReceived = false;
const mqttUrl = import.meta.env.VITE_MQTT_URL;
const options = {
  username: import.meta.env.VITE_MQTT_USERNAME,
  password: import.meta.env.VITE_MQTT_PASSWORD,
  clientId: 'ssig_frontend_browser_' + Math.random().toString(16).substr(2, 8)
};

console.log("Attempting to connect to MQTT broker at:", import.meta.env.VITE_MQTT_URL);
const client = mqtt.connect(mqttUrl, options);

client.on('connect', function () {
  console.log('Connected to MQTT broker');
  client.subscribe('alerts', function (err) {
    if (!err) {
      console.log('Subscribed to alerts topic');
    } else {
      console.error('Subscription error:', err);
    }
  });
});

client.on('error', function (error) {
  console.error('MQTT Client Error:', error);
});

client.on('reconnect', function () {
  console.log('MQTT client is reconnecting...');
});

client.on('offline', function () {
  console.log('MQTT client went offline.');
});

client.on('message', function (topic, message) {
  // We only care about messages from the 'alerts' topic now
  if (topic !== 'alerts') {
    return;
  }
  
  try {
    const alertData = JSON.parse(message.toString());
    if (!firstMqttAlertReceived) {
      appInstance.alertManager.clearAlerts();
      firstMqttAlertReceived = true;
    }
    appInstance.alertManager.createAlertCard(alertData);
    appInstance.alertManager.updateAlertSummary();
  } catch (e) {
    console.error('Failed to parse MQTT alert message:', e);
  }
});

// PPE Image Upload Logic
const uploadBtn = document.getElementById('uploadPPEBtn');
const fileInput = document.getElementById('ppeImageInput');
const modal = document.getElementById('ppeResultModal');
const closeModal = document.getElementById('closePPEModal');
const resultImage = document.getElementById('ppeResultImage');
const resultDetails = document.getElementById('ppeResultDetails');

if (uploadBtn && fileInput && modal && closeModal && resultImage && resultDetails) {
  uploadBtn.onclick = () => fileInput.click();

  fileInput.onchange = async () => {
    const file = fileInput.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('image', file);
    // Show loading...
    resultImage.innerHTML = 'Processing...';
    resultDetails.innerHTML = '';
    modal.style.display = 'block';
    // Send to backend (use correct backend URL)
    try {
      const res = await fetch('http://localhost:5001/api/check-ppe-image', { method: 'POST', body: formData });
      const data = await res.json();
      // Display result
      if (data.annotated_image) {
        resultImage.innerHTML = `<img src="data:image/png;base64,${data.annotated_image}" style="max-width:100%;">`;
      } else {
        resultImage.innerHTML = '';
      }
      if (data.detections && data.detections.length > 0) {
        resultDetails.innerHTML = data.detections.map(
          d => `<div class="alert-card critical">
                  <div class="alert-title">Person at ${d.person_box}</div>
                  <div class="alert-description">Missing PPE: ${d.missing_ppe ? d.missing_ppe.join(', ') : 'None'}</div>
                </div>`
        ).join('');
      } else {
        resultDetails.innerHTML = '<div class="alert-card info">No persons detected or all PPE present.</div>';
      }
    } catch (e) {
      resultImage.innerHTML = '';
      resultDetails.innerHTML = '<div class="alert-card warning">Error processing image.</div>';
    }
  };
  closeModal.onclick = () => { modal.style.display = 'none'; };
} 