import { alerts } from './config.js';

export class AlertManager {
    constructor() {
        this.alertsContainer = document.getElementById('alertsContainer');
        this.initializeAlerts();
        this.setupEventListeners();
    }

    initializeAlerts() {
        this.alertsContainer.innerHTML = '';
        alerts.forEach(alert => this.createAlertCard(alert));
        this.updateAlertSummary();
    }

    clearAlerts() {
        this.alertsContainer.innerHTML = '';
        this.updateAlertSummary();
    }

    createAlertCard(alert) {
        const alertCard = document.createElement('div');
        alertCard.className = `alert-card ${alert.type}`;
        alertCard.innerHTML = `
            <div class="alert-header">
                <div class="alert-icon">${alert.icon}</div>
                <div class="alert-info">
                    <div class="alert-title">${alert.title}</div>
                    <div class="alert-time">${alert.time}</div>
                </div>
                <div class="alert-priority ${alert.type}">${alert.priority}</div>
            </div>
            <div class="alert-description">
                ${alert.description}
            </div>
            <div class="alert-actions">
                <button class="alert-btn acknowledge">Acknowledge</button>
                <button class="alert-btn resolve">Resolve</button>
            </div>
        `;
        this.alertsContainer.appendChild(alertCard);
    }

    getAlertDataFromCard(alertCard) {
        // Helper function to extract alert data from the DOM card
        const title = alertCard.querySelector('.alert-title').textContent;
        const description = alertCard.querySelector('.alert-description').textContent.trim();
        const priority = alertCard.querySelector('.alert-priority').textContent;
        const type = alertCard.querySelector('.alert-priority').classList.contains('critical') ? 'critical' :
                     alertCard.querySelector('.alert-priority').classList.contains('warning') ? 'warning' : 'info';
        
        // The MQTT alert `id` is not on the card, so we'll use the title for now
        // A better approach would be to store the id in a data attribute on the card
        const id = title + '-' + new Date().getTime(); // Create a semi-unique ID

        return { id, type, title, description, priority };
    }

    async acknowledgeAlert(button) {
        const alertCard = button.closest('.alert-card');
        alertCard.style.opacity = '0.7';
        button.textContent = 'Acknowledged';
        button.disabled = true;
        button.style.background = 'rgba(100, 100, 100, 0.3)';

        // --- Send data to backend for logging ---
        const alertData = this.getAlertDataFromCard(alertCard);
        
        try {
            // Use environment variable for the API URL, with a local fallback
            const apiUrl = import.meta.env.VITE_BACKEND_API_URL || 'http://127.0.0.1:5001';
            const response = await fetch(`${apiUrl}/api/log-alert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(alertData),
            });
            const result = await response.json();
            if (response.ok) {
                console.log('Alert logged successfully:', result.message);
            } else {
                console.error('Failed to log alert:', result.message);
            }
        } catch (error) {
            console.error('Error sending alert to backend:', error);
        }
    }

    resolveAlert(button) {
        const alertCard = button.closest('.alert-card');
        alertCard.style.animation = 'slideOut 0.5s ease-in-out forwards';
        setTimeout(() => {
            alertCard.remove();
            this.updateAlertSummary();
        }, 500);
    }

    updateAlertSummary() {
        const criticalAlerts = document.querySelectorAll('.alert-card.critical').length;
        const warningAlerts = document.querySelectorAll('.alert-card.warning').length;
        const infoAlerts = document.querySelectorAll('.alert-card.info').length;

        document.querySelector('.summary-item.critical .summary-count').textContent = criticalAlerts;
        document.querySelector('.summary-item.warning .summary-count').textContent = warningAlerts;
        document.querySelector('.summary-item.info .summary-count').textContent = infoAlerts;
    }

    setupEventListeners() {
        this.alertsContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('acknowledge')) {
                this.acknowledgeAlert(e.target);
            } else if (e.target.classList.contains('resolve')) {
                this.resolveAlert(e.target);
            }
        });
    }
} 