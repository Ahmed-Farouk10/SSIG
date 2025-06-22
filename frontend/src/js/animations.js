// Create floating particles
export function createParticles() {
    const maxParticles = parseInt(import.meta.env.VITE_MAX_PARTICLES) || 20;
    const particleLifetime = parseInt(import.meta.env.VITE_PARTICLE_LIFETIME) || 25000;

    for (let i = 0; i < maxParticles; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 15 + 's';
        particle.style.animationDuration = (Math.random() * 10 + 10) + 's';
        document.body.appendChild(particle);
        
        setTimeout(() => {
            particle.remove();
        }, particleLifetime);
    }
}

// Start particle system after intro
export function startParticleSystem() {
    // Create initial particles
    createParticles();
    
    // Create new particles every 5 seconds
    setInterval(createParticles, 5000);
} 