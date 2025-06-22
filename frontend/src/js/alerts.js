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

    acknowledgeAlert(button) {
        const alertCard = button.closest('.alert-card');
        alertCard.style.opacity = '0.7';
        button.textContent = 'Acknowledged';
        button.disabled = true;
        button.style.background = 'rgba(100, 100, 100, 0.3)';
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