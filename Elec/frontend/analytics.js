// ============================================================
// Analytics Page - EnergyAI
// Real interaction data with historical trends and insights
// Updated: July 2026
// ============================================================

function getApiBase() {
    if (window.EnergyAIConfig && typeof window.EnergyAIConfig.getApiBase === 'function') {
        return window.EnergyAIConfig.getApiBase();
    }
    return 'http://localhost:8000';
}

function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, { signal: controller.signal }).finally(() => clearTimeout(timer));
}
const SHARED_DAILY_MODEL_KEY = 'energyai.shared.dailyModel';
const INTERACTION_HISTORY_KEY = 'energyai.interactionHistory';

let charts = {};
let currentPeriod = 7; // days shown in trend chart
let apiAvailable = false;

// ============================================================
//  INTERACTION HISTORY ACCESS
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

function getTrainingHistory() {
    return getInteractionHistory().filter(i => i.type === 'training');
}

function getForecastHistory() {
    return getInteractionHistory().filter(i => i.type === 'forecast');
}

function getRecentActivity(days = 30) {
    const history = getInteractionHistory();
    const cutoff = Date.now() - (days * 24 * 60 * 60 * 1000);
    return history.filter(i => new Date(i.timestamp).getTime() >= cutoff);
}

// ============================================================
//  THEME
// ============================================================

function toggleTheme() {
    const html = document.documentElement;
    const newTheme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
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
    updateChartsTheme();
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    if (sunIcon && moonIcon) {
        sunIcon.style.display = savedTheme === 'dark' ? 'none' : 'block';
        moonIcon.style.display = savedTheme === 'dark' ? 'block' : 'none';
    }
}

function updateChartsTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)';
    const tickColor = isDark ? '#94a3b8' : '#64748b';
    Object.values(charts).forEach(chart => {
        if (!chart || !chart.options) return;
        const scales = chart.options.scales || {};
        Object.values(scales).forEach(scale => {
            if (scale.grid) scale.grid.color = gridColor;
            if (scale.ticks) scale.ticks.color = tickColor;
        });
        chart.update('none');
    });
}

// ============================================================
//  API HELPERS
// ============================================================

async function checkApiHealth() {
    try {
        const res = await fetchWithTimeout(`${getApiBase()}/health`, 2000);
        if (res.ok) {
            apiAvailable = true;
            return await res.json();
        }
    } catch (_) { /* API offline */ }
    apiAvailable = false;
    return null;
}

async function fetchApiMetrics() {
    if (!apiAvailable) return null;
    try {
        const res = await fetchWithTimeout(`${getApiBase()}/metrics`, 3000);
        if (!res.ok) return null;
        const data = await res.json();
        return data?.validation_metrics || data;
    } catch (_) {}
    return null;
}

// ============================================================
//  LOCAL STORAGE MODEL
// ============================================================

function loadSharedForecastState() {
    try {
        const raw = localStorage.getItem(SHARED_DAILY_MODEL_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (e) {
        console.warn('Unable to load analytics forecast state:', e);
        return null;
    }
}

function syncMetricsToLocalStorage(metricsPayload) {
    if (!metricsPayload || !metricsPayload.training_snapshot || !metricsPayload.validation_metrics) {
        return null;
    }

    const s = metricsPayload.training_snapshot;
    const payload = {
        trained: true,
        historicalData: {
            consumption: Array.isArray(s.consumption) ? s.consumption : [],
            temperature: Array.isArray(s.temperature) ? s.temperature : [],
            humidity: Array.isArray(s.humidity) ? s.humidity : [],
            rainfall: Array.isArray(s.rainfall) ? s.rainfall : [],
            hasClasses: Array.isArray(s.has_classes) ? s.has_classes : [],
            dayOfWeek: Array.isArray(s.day_of_week) ? s.day_of_week : [],
            isWeekend: Array.isArray(s.is_weekend) ? s.is_weekend : [],
            dates: [],
        },
        trainingMetrics: metricsPayload.validation_metrics,
    };

    localStorage.setItem(SHARED_DAILY_MODEL_KEY, JSON.stringify(payload));
    return payload;
}

// ============================================================
//  DATA RESOLUTION (API → localStorage → defaults)
// ============================================================

async function resolveAnalyticsData() {
    // 1. Try API
    const health = await checkApiHealth();
    if (health && health.model_trained) {
        const apiMetrics = await fetchApiMetrics();
        if (apiMetrics) {
            const synced = syncMetricsToLocalStorage(apiMetrics);
            if (synced && synced.historicalData && synced.historicalData.consumption.length > 0) {
                return { source: 'local', payload: synced };
            }
            return { source: 'api', ...apiMetrics };
        }
    }

    // 2. Try localStorage model
    const payload = loadSharedForecastState();
    if (payload && payload.trained && payload.historicalData) {
        return { source: 'local', payload };
    }

    // 3. Static defaults
    return { source: 'static' };
}

// ============================================================
//  PERIOD SELECTOR & CHART CONTROLS
// ============================================================

function initPeriodSelector() {
    const select = document.getElementById('periodSelect');
    if (!select) return;
    select.addEventListener('change', () => {
        const map = { 'Last 7 Days': 7, 'Last 30 Days': 30, 'Last 90 Days': 90, 'Last Year': 365 };
        currentPeriod = map[select.value] || 7;
        refreshCharts();
    });
}

function initTrendButtons() {
    const buttons = document.querySelectorAll('.chart-controls .btn-text');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Re-slice trend data based on granularity label
            refreshTrendGranularity(btn.textContent.trim());
        });
    });
}

function refreshTrendGranularity(granularity) {
    if (!charts.trend) return;
    const payload = loadSharedForecastState();
    const consumption = payload?.historicalData?.consumption || defaultConsumption();
    const dates = payload?.historicalData?.dates || defaultDates();

    let sliceSize = 7;
    if (granularity === 'Weekly') sliceSize = Math.min(12, Math.floor(consumption.length / 7));
    else if (granularity === 'Monthly') sliceSize = Math.min(12, Math.floor(consumption.length / 30));

    if (granularity === 'Weekly') {
        // Aggregate into weeks
        const weeks = [], weekLabels = [];
        for (let i = 0; i < sliceSize; i++) {
            const chunk = consumption.slice(-(sliceSize - i) * 7, -(sliceSize - i - 1) * 7 || undefined);
            weeks.push(chunk.reduce((a, b) => a + b, 0));
            weekLabels.push(`Week ${i + 1}`);
        }
        charts.trend.data.labels = weekLabels;
        charts.trend.data.datasets[0].data = weeks;
        charts.trend.data.datasets[0].label = 'Weekly Consumption';
    } else if (granularity === 'Monthly') {
        const months = [], monthLabels = [];
        for (let i = 0; i < sliceSize; i++) {
            const chunk = consumption.slice(-(sliceSize - i) * 30, -(sliceSize - i - 1) * 30 || undefined);
            months.push(chunk.reduce((a, b) => a + b, 0));
            monthLabels.push(`Month ${i + 1}`);
        }
        charts.trend.data.labels = monthLabels;
        charts.trend.data.datasets[0].data = months;
        charts.trend.data.datasets[0].label = 'Monthly Consumption';
    } else {
        // Daily
        const slice = Math.min(currentPeriod, consumption.length);
        charts.trend.data.labels = dates.slice(-slice);
        charts.trend.data.datasets[0].data = consumption.slice(-slice);
        charts.trend.data.datasets[0].label = 'Daily Consumption';
    }
    charts.trend.update();
}

async function refreshCharts() {
    const data = await resolveAnalyticsData();
    updateAnalyticsFromData(data);
}

// ============================================================
//  DEFAULT FALLBACK DATA (Current Date Onwards)
// ============================================================

function defaultConsumption() {
    const baseLoad = 3200;
    const data = [];
    const today = new Date();
    for (let i = 29; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const dayOfWeek = d.getDay();
        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
        const weekendFactor = isWeekend ? 0.75 : 1.0;
        const randomVariation = 0.85 + Math.random() * 0.3;
        data.push(Math.round(baseLoad * weekendFactor * randomVariation));
    }
    return data;
}

function defaultDates() {
    const dates = [];
    const today = new Date();
    for (let i = 29; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        dates.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    }
    return dates;
}

function getCurrentDateInfo() {
    const today = new Date();
    return {
        today: today,
        formattedDate: today.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
        dayOfWeek: today.toLocaleDateString('en-US', { weekday: 'long' }),
        monthYear: today.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    };
}

// ============================================================
//  UPDATE UI FROM DATA
// ============================================================

function updateAnalyticsFromData(data) {
    let consumption = [], labels = [], trainingMetrics = null;
    let hasRealData = false;

    // Get interaction history for additional insights
    const history = getInteractionHistory();
    const trainingHistory = getTrainingHistory();
    const forecastHistory = getForecastHistory();
    const recentActivity = getRecentActivity(currentPeriod);

    if (data.source === 'api') {
        // API-only fallback (if snapshot unavailable)
        hasRealData = true;
        consumption = defaultConsumption();
        labels = defaultDates();
        trainingMetrics = data;
    } else if (data.source === 'local') {
        const { payload } = data;
        consumption = payload.historicalData.consumption || [];
        labels = payload.historicalData.dates || [];
        trainingMetrics = payload.trainingMetrics;
        hasRealData = true;
    } else {
        consumption = defaultConsumption();
        labels = defaultDates();
    }

    const slice = Math.min(currentPeriod, consumption.length);
    const trendValues = consumption.slice(-slice);
    const trendLabels = labels.slice(-slice);

    const latest = consumption.length ? consumption[consumption.length - 1] : 0;
    const avgConsumption = consumption.length
        ? consumption.reduce((a, b) => a + b, 0) / consumption.length
        : 3200;
    const peakDay = consumption.length ? Math.max(...consumption) : 0;
    const totalConsumption = Math.round(avgConsumption * slice);

    const rmse = trainingMetrics?.RMSE ?? 0;
    const mae = trainingMetrics?.MAE ?? 0;
    const r2 = trainingMetrics?.R2 ?? 0;

    // Schedule split from the available schedule context (class vs no-class).
    const scheduleFlags = (loadSharedForecastState()?.historicalData?.hasClasses) || [];
    const classDays = scheduleFlags.filter(f => f === 1).length;
    const noClassDays = scheduleFlags.filter(f => f === 0).length;
    const classShare = (classDays + noClassDays) > 0
        ? Math.round(classDays / (classDays + noClassDays) * 100)
        : 0;
    const noClassShare = (classDays + noClassDays) > 0 ? 100 - classShare : 0;

    // — Trend chart —
    if (charts.trend) {
        charts.trend.data.labels = trendLabels.length ? trendLabels : defaultDates().slice(-7);
        charts.trend.data.datasets[0].data = trendValues.length ? trendValues : defaultConsumption().slice(-7);
        charts.trend.data.datasets[0].label = hasRealData ? 'Daily Consumption' : 'Sample Consumption';
        charts.trend.update();
    }

    // — Day-type comparison (class vs no-class average) —
    if (charts.building) {
        const flags = scheduleFlags;
        const classVals = flags.length ? consumption.filter((_, i) => flags[i] === 1) : [];
        const noClassVals = flags.length ? consumption.filter((_, i) => flags[i] === 0) : [];
        const classMean = classVals.length ? classVals.reduce((a, b) => a + b, 0) / classVals.length : avgConsumption;
        const noClassMean = noClassVals.length ? noClassVals.reduce((a, b) => a + b, 0) / noClassVals.length : avgConsumption;
        charts.building.data.datasets[0].data = [
            Math.round(classMean),
            Math.round(noClassMean)
        ];
        charts.building.update();
    }

    // — Weekly consumption (sum per week) —
    if (charts.peak) {
        const weeks = [];
        for (let i = 0; i < 6; i++) {
            const chunk = consumption.slice(-(6 - i) * 7, (6 - i) === 0 ? undefined : -(6 - i - 1) * 7);
            weeks.push(Math.round(chunk.reduce((a, b) => a + b, 0)));
        }
        charts.peak.data.datasets[0].data = weeks;
        charts.peak.update();
    }

    // — Schedule distribution (class vs no-class share) —
    if (charts.efficiency) {
        if (classShare > 0 || noClassShare > 0) {
            charts.efficiency.data.datasets[0].data = [classShare, noClassShare];
        }
        charts.efficiency.update();
    }

    // — Stat cards —
    const statValues = document.querySelectorAll('.stat-value');
    const statChanges = document.querySelectorAll('.stat-change');
    
    if (statValues.length >= 4) {
        statValues[0].textContent = `${totalConsumption.toLocaleString()} kWh`;
        statValues[1].textContent = `₱${Math.round(totalConsumption * 12.383).toLocaleString('en-PH')}`;
        statValues[2].textContent = `${Math.round(peakDay).toLocaleString()} kWh`;
        statValues[3].textContent = `${slice}`;
        
        // Update stat changes with real data
        if (statChanges.length >= 4) {
            const dateInfo = getCurrentDateInfo();
            
            // Consumption change
            if (consumption.length >= 2) {
                const prevAvg = consumption.slice(0, -slice).reduce((a, b) => a + b, 0) / Math.max(1, consumption.length - slice);
                const change = ((avgConsumption - prevAvg) / prevAvg * 100).toFixed(1);
                statChanges[0].textContent = `${change > 0 ? '+' : ''}${change}% vs prior period`;
                statChanges[0].className = change < 0 ? 'stat-change positive' : 'stat-change negative';
            } else {
                statChanges[0].textContent = 'Selected period';
            }
            
            // Cost note
            statChanges[1].textContent = 'Reference rate ₱12.383/kWh';
            
            // Peak day note
            statChanges[2].textContent = 'Highest daily value in period';
            
            // Days covered note
            statChanges[3].textContent = 'Daily rows shown';
        }
    }

    // — Summary text —
    const subtitle = document.querySelector('.card .card-body p');
    if (subtitle) {
        const dateInfo = getCurrentDateInfo();
        if (data.source === 'api') {
            subtitle.textContent = `Data served by the EnergyAI API. Last updated: ${dateInfo.formattedDate}.`;
        } else if (data.source === 'local' && hasRealData) {
            const trainCount = trainingHistory.length;
            const forecastCount = forecastHistory.length;
            subtitle.textContent = `Analytics based on ${trainCount} training session${trainCount !== 1 ? 's' : ''} and ${forecastCount} forecast${forecastCount !== 1 ? 's' : ''}. Model metrics: RMSE ${rmse.toFixed(1)} kWh, MAE ${mae.toFixed(1)} kWh, R² ${r2.toFixed(3)}. Data as of ${dateInfo.formattedDate}.`;
        } else {
            subtitle.textContent = `No trained model found. Model training is an administrator task in the Models workspace. Today is ${dateInfo.formattedDate}.`;
        }
    }

    // — API status badge —
    updateApiStatus(data.source, hasRealData, history.length);
}

function updateApiStatus(source, hasRealData, historyCount) {
    let badge = document.getElementById('apiStatusBadge');
    if (!badge) return;
    
    const map = {
        api:    { text: 'Live API', cls: 'badge-green' },
        local:  { text: hasRealData ? `${historyCount} Activities` : 'Cached Model', cls: hasRealData ? 'badge-green' : 'badge-blue' },
        static: { text: 'No Model', cls: 'badge-gray' }
    };
    
    const { text, cls } = map[source] || map.static;
    badge.textContent = text;
    badge.className = `api-status-badge ${cls}`;
}

// ============================================================
//  CHART INITIALIZATION
// ============================================================

function initCharts() {
    const today = getCurrentDateInfo().today;
    
    const trendCtx = document.getElementById('trendChart')?.getContext('2d');
    if (trendCtx) {
        charts.trend = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: defaultDates().slice(-7),
                datasets: [{
                    label: 'Daily Consumption',
                    data: defaultConsumption().slice(-7),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16,185,129,0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} kWh`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: { display: true, text: 'kWh' },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    const buildingCtx = document.getElementById('buildingChart')?.getContext('2d');
    if (buildingCtx) {
        charts.building = new Chart(buildingCtx, {
            type: 'bar',
            data: {
                labels: ['Class Days', 'No-Class Days'],
                datasets: [{
                    label: 'Average Consumption (kWh)',
                    data: [3200, 2800],
                    backgroundColor: ['#10b981', '#f59e0b'],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.parsed.y.toLocaleString()} kWh/day`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'kWh/day' },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    const peakCtx = document.getElementById('peakChart')?.getContext('2d');
    if (peakCtx) {
        charts.peak = new Chart(peakCtx, {
            type: 'bar',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
                datasets: [{
                    label: 'Weekly Consumption (kWh)',
                    data: [0, 0, 0, 0, 0, 0],
                    backgroundColor: '#f59e0b',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.parsed.y.toLocaleString()} kWh`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'kWh' },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    const efficiencyCtx = document.getElementById('efficiencyChart')?.getContext('2d');
    if (efficiencyCtx) {
        charts.efficiency = new Chart(efficiencyCtx, {
            type: 'doughnut',
            data: {
                labels: ['Class Days', 'No-Class Days'],
                datasets: [{
                    data: [50, 50],
                    backgroundColor: ['#10b981', '#f59e0b'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed.toFixed(1)}%`
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }
}

// ============================================================
//  INJECT API STATUS BADGE INTO HEADER
// ============================================================

function injectStatusBadge() {
    const header = document.querySelector('.header-left');
    if (!header || document.getElementById('apiStatusBadge')) return;
    const badge = document.createElement('span');
    badge.id = 'apiStatusBadge';
    badge.className = 'api-status-badge badge-gray';
    badge.textContent = 'Connecting…';
    header.appendChild(badge);

    // Inline styles so no CSS changes needed
    const style = document.createElement('style');
    style.textContent = `
        .api-status-badge {
            display: inline-block;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
            margin-top: 6px;
            letter-spacing: 0.4px;
            text-transform: uppercase;
        }
        .badge-green  { background: rgba(16,185,129,0.15); color: #10b981; }
        .badge-blue   { background: rgba(59,130,246,0.15); color: #3b82f6; }
        .badge-gray   { background: rgba(100,116,139,0.15); color: #64748b; }
    `;
    document.head.appendChild(style);
}

// ============================================================
//  INIT
// ============================================================

window.addEventListener('load', async () => {
    loadTheme();
    injectStatusBadge();
    initCharts();
    initPeriodSelector();
    initTrendButtons();

    const data = await resolveAnalyticsData();
    updateAnalyticsFromData(data);

    // Poll every 30 seconds if API is available
    if (apiAvailable) {
        setInterval(refreshCharts, 30_000);
    }
});

// React to model updates from other tabs (e.g. dashboard trains a model)
window.addEventListener('storage', event => {
    if (event.key === SHARED_DAILY_MODEL_KEY || event.key === INTERACTION_HISTORY_KEY) {
        console.log('Analytics: Detected data update, refreshing charts...');
        refreshCharts();
    }
});
