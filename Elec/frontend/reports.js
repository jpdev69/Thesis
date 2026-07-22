// ============================================================
// Reports Page - EnergyAI
// Real interaction tracking, report generation, and scheduling
// ============================================================

const INTERACTION_HISTORY_KEY = 'energyai.interactionHistory';
const SCHEDULED_REPORTS_KEY = 'energyai.scheduledReports';
const SHARED_DAILY_MODEL_KEY = 'energyai.shared.dailyModel';

// ============================================================
// INTERACTION HISTORY TRACKING
// ============================================================

function getInteractionHistory() {
    try {
        const raw = localStorage.getItem(INTERACTION_HISTORY_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (error) {
        console.warn('Error loading interaction history:', error);
        return [];
    }
}

function saveInteraction(type, data) {
    const history = getInteractionHistory();
    const interaction = {
        id: Date.now(),
        type: type, // 'training', 'forecast', 'export'
        timestamp: new Date().toISOString(),
        data: data
    };
    history.unshift(interaction); // Add to beginning
    
    // Keep only last 50 interactions
    if (history.length > 50) {
        history.splice(50);
    }
    
    localStorage.setItem(INTERACTION_HISTORY_KEY, JSON.stringify(history));
}

// ============================================================
// SCHEDULED REPORTS
// ============================================================

function getScheduledReports() {
    try {
        const raw = localStorage.getItem(SCHEDULED_REPORTS_KEY);
        return raw ? JSON.parse(raw) : getDefaultScheduledReports();
    } catch (error) {
        console.warn('Error loading scheduled reports:', error);
        return getDefaultScheduledReports();
    }
}

function getDefaultScheduledReports() {
    return [
        {
            id: 1,
            name: 'Daily Energy Summary',
            frequency: 'Daily at 8:00 AM',
            recipients: 'admin@energy.ai',
            nextRun: 'Tomorrow, 8:00 AM',
            active: true
        },
        {
            id: 2,
            name: 'Weekly Performance',
            frequency: 'Weekly on Monday',
            recipients: 'team@energy.ai',
            nextRun: 'Monday, 9:00 AM',
            active: true
        },
        {
            id: 3,
            name: 'Monthly Sustainability',
            frequency: 'Monthly on 1st',
            recipients: 'management@energy.ai',
            nextRun: 'Aug 1, 2026',
            active: true
        }
    ];
}

function saveScheduledReports(reports) {
    localStorage.setItem(SCHEDULED_REPORTS_KEY, JSON.stringify(reports));
}

// ============================================================
// REPORT GENERATION
// ============================================================

function generateReport(template) {
    const modelData = loadSharedForecastState();
    const history = getInteractionHistory();
    
    if (!modelData || !modelData.trained) {
        alert('No trained model available. Please train a model first on the Dashboard.');
        return;
    }
    
    // Track this interaction
    saveInteraction('report_generation', {
        template: template,
        modelTrained: modelData.trained,
        dataPoints: modelData.historicalData?.consumption?.length || 0
    });
    
    alert(`Generating ${template} report based on current model data...\n\nThis will be implemented in the full version.`);
    
    // Refresh the recent reports section
    renderRecentReports();
}

function openReportGenerator() {
    const modelData = loadSharedForecastState();
    
    if (!modelData || !modelData.trained) {
        alert('No trained model available.\n\nPlease go to the Dashboard and:\n1. Train a model with your data\n2. Generate a forecast\n3. Return here to create reports');
        return;
    }
    
    const templates = [
        'Daily Summary',
        'Weekly Report', 
        'Monthly Analysis',
        'Cost Analysis',
        'Building Comparison',
        'Sustainability Report'
    ];
    
    const choice = prompt(
        'Select a report template to generate:\n\n' +
        templates.map((t, i) => `${i + 1}. ${t}`).join('\n') +
        '\n\nEnter number (1-6):'
    );
    
    const index = parseInt(choice) - 1;
    if (index >= 0 && index < templates.length) {
        generateReport(templates[index]);
    }
}

// ============================================================
// UI RENDERING
// ============================================================

function renderRecentReports() {
    const container = document.querySelector('.card-body > div');
    if (!container) return;
    
    const history = getInteractionHistory();
    const modelData = loadSharedForecastState();
    
    // Filter for report-generating interactions (training and forecasts)
    const reportableInteractions = history.filter(i => 
        i.type === 'training' || i.type === 'forecast' || i.type === 'report_generation'
    );
    
    if (reportableInteractions.length === 0) {
        container.innerHTML = `
            <div style="padding: 40px; text-align: center; color: var(--text-secondary);">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 16px; opacity: 0.3;">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <p style="font-size: 16px; margin-bottom: 8px;">No reports generated yet</p>
                <p style="font-size: 14px;">Train a model and generate forecasts on the Dashboard to see reports here.</p>
            </div>
        `;
        return;
    }
    
    // Generate report cards from interactions
    let html = '';
    const reportsToShow = reportableInteractions.slice(0, 5); // Show last 5
    
    reportsToShow.forEach(interaction => {
        const date = new Date(interaction.timestamp);
        const dateStr = date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        let title = '';
        let details = '';
        let size = '1.2 MB';
        
        if (interaction.type === 'training') {
            title = `Model Training Report - ${date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}`;
            const metrics = interaction.data?.metrics || {};
            details = `RMSE: ${(metrics.RMSE || 0).toFixed(2)} kWh • R²: ${(metrics.R2 || 0).toFixed(3)} • ${interaction.data?.dataPoints || 0} data points`;
        } else if (interaction.type === 'forecast') {
            title = `Forecast Report - ${interaction.data?.days || 7} Days`;
            const total = interaction.data?.totalConsumption || 0;
            const cost = interaction.data?.totalCost || 0;
            details = `${total.toFixed(2)} kWh • ₱${cost.toFixed(2)} estimated cost`;
        } else if (interaction.type === 'report_generation') {
            title = `${interaction.data?.template || 'Custom'} Report`;
            details = `Based on ${interaction.data?.dataPoints || 0} data points`;
        }
        
        html += `
            <div style="display: flex; align-items: center; padding: 16px; background: var(--bg-tertiary); border-radius: 8px;">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" style="margin-right: 16px;">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 4px;">${title}</div>
                    <div style="font-size: 13px; color: var(--text-secondary);">Generated on ${dateStr} • ${size}</div>
                    <div style="font-size: 12px; color: var(--text-tertiary); margin-top: 4px;">${details}</div>
                </div>
                <button class="btn-secondary" onclick="downloadReport(${interaction.id})">Download PDF</button>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function renderScheduledReports() {
    const tbody = document.querySelector('tbody');
    if (!tbody) return;
    
    const reports = getScheduledReports();
    
    let html = '';
    reports.forEach(report => {
        html += `
            <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 16px; font-weight: 500;">${report.name}</td>
                <td style="padding: 16px;">${report.frequency}</td>
                <td style="padding: 16px;">${report.recipients}</td>
                <td style="padding: 16px;">${report.nextRun}</td>
                <td style="padding: 16px;">
                    <span class="badge ${report.active ? 'success' : 'warning'}">
                        ${report.active ? 'Active' : 'Paused'}
                    </span>
                </td>
                <td style="padding: 16px;">
                    <button class="btn-text" onclick="editScheduledReport(${report.id})">Edit</button>
                    <button class="btn-text" onclick="toggleScheduledReport(${report.id})" style="margin-left: 8px;">
                        ${report.active ? 'Pause' : 'Resume'}
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

function renderReportTemplates() {
    const container = document.querySelectorAll('.card-body')[1];
    if (!container) return;
    
    const templates = [
        { name: 'Daily Summary', icon: 'activity', description: 'Daily consumption and forecast' },
        { name: 'Weekly Report', icon: 'calendar', description: 'Weekly trends and insights' },
        { name: 'Monthly Analysis', icon: 'trending-up', description: 'Monthly performance analysis' },
        { name: 'Cost Analysis', icon: 'dollar-sign', description: 'Cost breakdown and savings' },
        { name: 'Building Comparison', icon: 'home', description: 'Compare building performance' },
        { name: 'Sustainability Report', icon: 'leaf', description: 'Environmental impact report' }
    ];
    
    let html = '<div style="display: flex; flex-direction: column; gap: 12px;">';
    
    templates.forEach(template => {
        html += `
            <button class="btn-secondary full-width" style="justify-content: flex-start;" onclick="generateReport('${template.name}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px;">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
                <div style="flex: 1; text-align: left;">
                    <div style="font-weight: 500;">${template.name}</div>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">${template.description}</div>
                </div>
            </button>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// ============================================================
// ACTIONS
// ============================================================

function downloadReport(interactionId) {
    const history = getInteractionHistory();
    const interaction = history.find(i => i.id === interactionId);
    
    if (!interaction) {
        alert('Report not found.');
        return;
    }
    
    // Track download interaction
    saveInteraction('download', {
        reportId: interactionId,
        reportType: interaction.type
    });
    
    alert(`Downloading report from ${new Date(interaction.timestamp).toLocaleString()}...\n\nPDF generation will be implemented in the full version.`);
}

function editScheduledReport(reportId) {
    const reports = getScheduledReports();
    const report = reports.find(r => r.id === reportId);
    
    if (!report) return;
    
    alert(`Editing scheduled report: ${report.name}\n\nThis feature will be implemented in the full version.`);
}

function toggleScheduledReport(reportId) {
    const reports = getScheduledReports();
    const report = reports.find(r => r.id === reportId);
    
    if (!report) return;
    
    report.active = !report.active;
    saveScheduledReports(reports);
    renderScheduledReports();
}

function loadSharedForecastState() {
    try {
        const raw = localStorage.getItem(SHARED_DAILY_MODEL_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (error) {
        console.warn('Unable to load forecast state:', error);
        return null;
    }
}

// ============================================================
// THEME MANAGEMENT
// ============================================================

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

// ============================================================
// INITIALIZATION
// ============================================================

window.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    renderRecentReports();
    renderScheduledReports();
    renderReportTemplates();
    
    // Update subtitle with model info
    const modelData = loadSharedForecastState();
    const subtitle = document.querySelector('.header-left .subtitle');
    
    if (subtitle && modelData && modelData.trained) {
        const consumption = modelData.historicalData?.consumption || [];
        const avgConsumption = consumption.length ? consumption.reduce((a, b) => a + b, 0) / consumption.length : 0;
        const dataPoints = consumption.length;
        subtitle.textContent = `${dataPoints} data points tracked • ${Math.round(avgConsumption).toLocaleString()} kWh average consumption`;
    }
});

// Listen for storage changes (when training/forecasting happens on dashboard)
window.addEventListener('storage', (event) => {
    if (event.key === SHARED_DAILY_MODEL_KEY || event.key === INTERACTION_HISTORY_KEY) {
        renderRecentReports();
    }
});
