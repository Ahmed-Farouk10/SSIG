import { sensors } from './config.js';

export class SensorManager {
    constructor() {
        this.sensorsGrid = document.getElementById('sensorsGrid');
        this.initializeSensors();
    }

    initializeSensors() {
        this.sensorsGrid.innerHTML = '';
        sensors.forEach(sensor => this.createSensorCard(sensor));
    }

    createSensorCard(sensor) {
        const sensorCard = document.createElement('div');
        sensorCard.className = 'sensor-card';
        sensorCard.innerHTML = `
            <div class="sensor-header">
                <div class="sensor-icon">${sensor.icon}</div>
                <div>
                    <div class="sensor-name">${sensor.name}</div>
                    <div class="sensor-status">
                        <span>●</span>
                        <span>${sensor.status}</span>
                    </div>
                </div>
            </div>
            <div class="sensor-value">${sensor.value}</div>
        `;
        this.sensorsGrid.appendChild(sensorCard);
    }

    updateSensorData() {
        // Simulate sensor data updates
        const sensorValues = document.querySelectorAll('.sensor-value');
        sensorValues.forEach(value => {
            // Add subtle animations or data updates here if needed
        });
    }
} 