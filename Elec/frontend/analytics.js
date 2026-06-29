// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    
    if (newTheme === 'dark') {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
    }
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    
    if (savedTheme === 'dark') {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    }
}

// Initialize charts
function initCharts() {
    // Trend Chart
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'This Week',
                data: [3200, 3100, 3400, 3300, 3500, 2800, 2600],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4
            }, {
                label: 'Last Week',
                data: [3500, 3400, 3600, 3500, 3700, 3100, 2900],
                borderColor: '#94a3b8',
                backgroundColor: 'rgba(148, 163, 184, 0.1)',
                tension: 0.4,
                borderDash: [5, 5]
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'kWh' } }
            }
        }
    });

    // Building Chart
    const buildingCtx = document.getElementById('buildingChart').getContext('2d');
    new Chart(buildingCtx, {
        type: 'bar',
        data: {
            labels: ['Building A', 'Building B', 'Building C', 'Building D', 'Building E'],
            datasets: [{
                label: 'Consumption (kWh)',
                data: [5200, 4800, 6100, 3900, 4500],
                backgroundColor: ['#10b981', '#14b8a6', '#22c55e', '#34d399', '#6ee7b7']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });

    // Peak Hours Chart
    const peakCtx = document.getElementById('peakChart').getContext('2d');
    new Chart(peakCtx, {
        type: 'line',
        data: {
            labels: ['12AM', '4AM', '8AM', '12PM', '4PM', '8PM'],
            datasets: [{
                label: 'Average Load (kW)',
                data: [80, 65, 120, 150, 187, 140],
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });

    // Efficiency Chart
    const efficiencyCtx = document.getElementById('efficiencyChart').getContext('2d');
    new Chart(efficiencyCtx, {
        type: 'doughnut',
        data: {
            labels: ['Efficient', 'Moderate', 'Needs Improvement'],
            datasets: [{
                data: [65, 25, 10],
                backgroundColor: ['#10b981', '#fbbf24', '#ef4444']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

window.addEventListener('load', () => {
    loadTheme();
    initCharts();
});
