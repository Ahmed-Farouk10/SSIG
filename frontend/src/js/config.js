// Sensor configuration
export const sensors = [
    {
        id: 'lidar',
        name: 'LiDAR',
        icon: '📡',
        status: 'Active',
        value: '360° Scanning'
    },
    {
        id: 'flame',
        name: 'Flame Module',
        icon: '🔥',
        status: 'Monitoring',
        value: 'No Fire Detected'
    },
    {
        id: 'eco',
        name: 'ECO Module',
        icon: '🌿',
        status: 'Online',
        value: 'Temp: 24°C | Humidity: 45%\nLight: 1200lx | Press: 1013hPa'
    },
    {
        id: 'co2',
        name: 'CO2 Gas Sensor',
        icon: '💨',
        status: 'Active',
        value: '420 ppm'
    },
    {
        id: 'dust',
        name: 'Dust Sensor',
        icon: '🌫️',
        status: 'Monitoring',
        value: 'PM2.5: 12 μg/m³'
    },
    {
        id: 'thermopile',
        name: 'Thermopile Laser',
        icon: '🌡️',
        status: 'Scanning',
        value: 'Surface: 22.5°C'
    },
    {
        id: 'motion',
        name: 'Microwave Motion',
        icon: '📶',
        status: 'Detecting',
        value: 'No Motion'
    },
    {
        id: 'pir',
        name: 'PIR Sensor',
        icon: '👁️',
        status: 'Standby',
        value: 'Ready'
    }
];

// Alert configuration
export const alerts = [
    {
        id: 1,
        type: 'critical',
        icon: '🔥',
        title: 'CRITICAL: Fire Detection',
        time: '2 minutes ago',
        description: 'Flame detected in Zone B-3. Immediate evacuation required. Fire suppression system activated.',
        priority: 'HIGH'
    },
    {
        id: 2,
        type: 'warning',
        icon: '⚠️',
        title: 'WARNING: Unauthorized Access',
        time: '5 minutes ago',
        description: 'Motion detected in restricted area during off-hours. PIR sensor triggered at entrance gate.',
        priority: 'MEDIUM'
    },
    {
        id: 3,
        type: 'info',
        icon: '💨',
        title: 'INFO: Air Quality Alert',
        time: '12 minutes ago',
        description: 'CO2 levels elevated (450 ppm). Recommend increased ventilation in work area.',
        priority: 'LOW'
    }
]; 