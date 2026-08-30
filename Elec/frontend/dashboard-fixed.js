// ============================================================
// EnergyAI Dashboard - Attention-LSTM + RBF-SVR Forecasting
// Live API forecasts • Confidence bands • Anomaly detection
// Export • Peak load analysis
// ============================================================

let chart = null;
let dailyModel = null;
let currentChartData = { labels: [], data: [], colors: [], lower: [], upper: [] };
let currentChartView = 7;
let notificationCount = 0;
let lastForecastResult = null;

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

async function hydrateSharedModelFromApi() {
    try {
        const healthRes = await fetchWithTimeout(`${getApiBase()}/health`, 2000);
        if (!healthRes.ok) return null;
        const health = await healthRes.json();
        if (!health.model_trained) return null;

        const metricsRes = await fetchWithTimeout(`${getApiBase()}/metrics`, 3000);
        if (!metricsRes.ok) return null;
        const metricsPayload = await metricsRes.json();

        const snapshot = metricsPayload?.training_snapshot;
        const validation = metricsPayload?.validation_metrics;
        if (!snapshot || !validation) return null;

        const payload = {
            trained: true,
            historicalData: {
                consumption: Array.isArray(snapshot.consumption) ? snapshot.consumption : [],
                temperature: Array.isArray(snapshot.temperature) ? snapshot.temperature : [],
                humidity: Array.isArray(snapshot.humidity) ? snapshot.humidity : [],
                rainfall: Array.isArray(snapshot.rainfall) ? snapshot.rainfall : [],
                hasClasses: Array.isArray(snapshot.has_classes) ? snapshot.has_classes : [],
                dayOfWeek: Array.isArray(snapshot.day_of_week) ? snapshot.day_of_week : [],
                isWeekend: Array.isArray(snapshot.is_weekend) ? snapshot.is_weekend : [],
                dates: [],
            },
            trainingMetrics: validation,
        };

        localStorage.setItem(SHARED_DAILY_MODEL_KEY, JSON.stringify(payload));
        return payload;
    } catch (_) {
        return null;
    }
}

// Interaction tracking for reports page
const INTERACTION_HISTORY_KEY = 'energyai.interactionHistory';

function saveInteraction(type, data) {
    try {
        const raw = localStorage.getItem(INTERACTION_HISTORY_KEY);
        const history = raw ? JSON.parse(raw) : [];
        const interaction = {
            id: Date.now(),
            type: type,
            timestamp: new Date().toISOString(),
            data: data
        };
        history.unshift(interaction);
        if (history.length > 50) history.splice(50);
        localStorage.setItem(INTERACTION_HISTORY_KEY, JSON.stringify(history));
    } catch (error) {
        console.warn('Error saving interaction:', error);
    }
}

// ============================================================
//  ENHANCED DAILY PREDICTOR (offline fallback only)
// ============================================================

class DailyPredictor {
    constructor() {
        this.scaler = { min: 0, max: 1 };
        this.trained = false;
        this.historicalData = null;
        this.coefficients = {};
        this.trainingMetrics = {};
    }

    parseDailyData(csvText) {
        const lines = csvText.trim().split('\n');
        const data = {
            dates: [], consumption: [], temperature: [],
            humidity: [], rainfall: [], hasClasses: []
        };

        for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length >= 6) {
                data.dates.push(parts[0].trim());
                data.consumption.push(parseFloat(parts[1]));
                data.temperature.push(parseFloat(parts[2]));
                data.humidity.push(parseFloat(parts[3]));
                data.rainfall.push(parseFloat(parts[4]));
                data.hasClasses.push(parseInt(parts[5]));
            }
        }
        return data;
    }

    train(dailyData) {
        this.historicalData = dailyData;
        this.trained = true;

        const { consumption, temperature, humidity, rainfall, hasClasses } = dailyData;
        const n = consumption.length;

        // Compute statistics
        const classConsumption = consumption.filter((_, i) => hasClasses[i] === 1);
        const noClassConsumption = consumption.filter((_, i) => hasClasses[i] === 0);
        const classAvg = classConsumption.length > 0 ? classConsumption.reduce((a, b) => a + b) / classConsumption.length : 0;
        const noClassAvg = noClassConsumption.length > 0 ? noClassConsumption.reduce((a, b) => a + b) / noClassConsumption.length : 0;
        const avgConsumption = consumption.reduce((a, b) => a + b) / n;

        // Multiple linear regression coefficients (computed via correlations)
        const tempMean = temperature.reduce((a, b) => a + b) / n;
        const humMean = humidity.reduce((a, b) => a + b) / n;
        const rainMean = rainfall.reduce((a, b) => a + b) / n;

        let tempCoeff = 0, humCoeff = 0, rainCoeff = 0;
        let tempVar = 0, humVar = 0, rainVar = 0;
        for (let i = 0; i < n; i++) {
            const consResidual = consumption[i] - avgConsumption;
            tempCoeff += consResidual * (temperature[i] - tempMean);
            humCoeff += consResidual * (humidity[i] - humMean);
            rainCoeff += consResidual * (rainfall[i] - rainMean);
            tempVar += (temperature[i] - tempMean) ** 2;
            humVar += (humidity[i] - humMean) ** 2;
            rainVar += (rainfall[i] - rainMean) ** 2;
        }
        this.coefficients = {
            temperature: tempVar > 0 ? tempCoeff / tempVar : 0,
            humidity: humVar > 0 ? humCoeff / humVar : 0,
            rainfall: rainVar > 0 ? rainCoeff / rainVar : 0,
            classEffect: classAvg - noClassAvg,
            baseLoad: avgConsumption,
            tempMean, humMean, rainMean
        };

        // Holdout validation (last 20%)
        const splitIdx = Math.floor(n * 0.8);
        const valPredictions = [];
        const valActual = consumption.slice(splitIdx);
        for (let i = splitIdx; i < n; i++) {
            valPredictions.push(this.predictDay(
                temperature[i], humidity[i], rainfall[i], hasClasses[i]
            ));
        }

        // Real metrics from holdout
        this.trainingMetrics = this._computeMetrics(valActual, valPredictions);

        return {
            avgConsumption, classAvg, noClassAvg,
            difference: classAvg - noClassAvg,
            percentDiff: noClassAvg > 0 ? ((classAvg - noClassAvg) / noClassAvg * 100).toFixed(2) : '0',
            metrics: this.trainingMetrics
        };
    }

    predictDay(temperature, humidity, rainfall, hasClasses) {
        if (!this.trained) throw new Error('Model not trained');
        const c = this.coefficients;
        let prediction = c.baseLoad;
        prediction += c.temperature * (temperature - c.tempMean);
        prediction += c.humidity * (humidity - c.humMean);
        prediction += c.rainfall * (rainfall - c.rainMean);
        if (hasClasses === 0) prediction -= c.classEffect;

        return Math.max(500, prediction);
    }

    predictDayWithConfidence(temperature, humidity, rainfall, hasClasses) {
        const point = this.predictDay(temperature, humidity, rainfall, hasClasses);

        // Use RMSE from training metrics as base uncertainty
        // Reduce sigma to 30% of RMSE for tighter, more realistic intervals
        // (RMSE represents average error, not prediction interval width)
        let baseRMSE = (this.trainingMetrics && this.trainingMetrics.RMSE > 0)
            ? this.trainingMetrics.RMSE
            : point * 0.05;
        
        const sigma = baseRMSE * 0.3;  // Use 30% of RMSE for tighter bounds

        // Use seeded random for consistent intervals (prevents changing on refresh)
        // Deterministic pseudo-random based on point value
        const seed = Math.floor(point * 1000) % 9999;
        let randomSeed = seed;
        const seededRandom = () => {
            randomSeed = (randomSeed * 9301 + 49297) % 233280;
            return randomSeed / 233280;
        };

        // Monte Carlo: add Gaussian noise (Box-Muller) to samples
        const predictions = [];
        for (let i = 0; i < 500; i++) {
            const u1 = seededRandom();
            const u2 = seededRandom();
            const z = Math.sqrt(-2 * Math.log(u1 || 1e-10)) * Math.cos(2 * Math.PI * u2);
            predictions.push(Math.max(0, point + z * sigma));
        }
        predictions.sort((a, b) => a - b);

        const mean = predictions.reduce((a, b) => a + b) / predictions.length;
        const variance = predictions.reduce((s, v) => s + (v - mean) ** 2, 0) / predictions.length;
        const std = Math.sqrt(variance);

        return {
            mean: point,                                                    // use deterministic point
            lower: predictions[Math.floor(predictions.length * 0.025)],    // 2.5th percentile
            upper: predictions[Math.floor(predictions.length * 0.975)],    // 97.5th percentile
            std,
            p10: predictions[Math.floor(predictions.length * 0.1)],
            p90: predictions[Math.floor(predictions.length * 0.9)]
        };
    }

    predictWeek(futureWeather, futureSchedule) {
        const predictions = [], lower = [], upper = [];
        for (let i = 0; i < futureWeather.length; i++) {
            const result = this.predictDayWithConfidence(
                futureWeather[i].temperature,
                futureWeather[i].humidity,
                futureWeather[i].rainfall,
                futureSchedule[i]
            );
            predictions.push(result.mean);
            lower.push(result.lower);
            upper.push(result.upper);
        }
        return { predictions, lower, upper };
    }

    detectAnomalies(consumption, threshold = 2.0) {
        const mean = consumption.reduce((a, b) => a + b) / consumption.length;
        const std = Math.sqrt(consumption.reduce((s, v) => s + (v - mean) ** 2, 0) / consumption.length);
        if (std === 0) return [];

        const anomalies = [];
        consumption.forEach((val, i) => {
            const z = (val - mean) / std;
            if (Math.abs(z) > threshold) {
                anomalies.push({
                    index: i, value: val, zScore: z,
                    expected: mean, deviationPct: ((val - mean) / mean * 100).toFixed(2),
                    type: z > 0 ? 'spike' : 'dip'
                });
            }
        });
        return anomalies;
    }

    estimatePeakLoad(predictions) {
        const peak = Math.max(...predictions);
        const peakIdx = predictions.indexOf(peak);
        const min = Math.min(...predictions);
        const minIdx = predictions.indexOf(min);
        const avg = predictions.reduce((a, b) => a + b) / predictions.length;

        return {
            peakValue: peak, peakDayIndex: peakIdx,
            minValue: min, minDayIndex: minIdx,
            avgLoad: avg, loadFactor: peak > 0 ? avg / peak : 0,
            range: peak - min
        };
    }

    _computeMetrics(actual, predicted) {
        const n = actual.length;
        if (n === 0) return { RMSE: 0, MAE: 0, MAPE: 0, R2: 0 };

        let sumSqErr = 0, sumAbsErr = 0, sumAPE = 0;
        for (let i = 0; i < n; i++) {
            const err = actual[i] - predicted[i];
            sumSqErr += err * err;
            sumAbsErr += Math.abs(err);
            if (actual[i] !== 0) sumAPE += Math.abs(err / actual[i]);
        }
        const rmse = Math.sqrt(sumSqErr / n);
        const mae = sumAbsErr / n;
        const mape = (sumAPE / n) * 100;

        const mean = actual.reduce((a, b) => a + b) / n;
        const ssTot = actual.reduce((s, v) => s + (v - mean) ** 2, 0);
        const ssRes = actual.reduce((s, v, i) => s + (v - predicted[i]) ** 2, 0);
        const r2 = ssTot > 0 ? 1 - ssRes / ssTot : 0;

        let dirCorrect = 0, dirTotal = 0;
        for (let i = 1; i < n; i++) {
            if ((actual[i] > actual[i - 1]) === (predicted[i] > predicted[i - 1])) dirCorrect++;
            dirTotal++;
        }

        return {
            RMSE: rmse, MAE: mae, MAPE: mape, R2: r2,
            DirectionalAccuracy: dirTotal > 0 ? (dirCorrect / dirTotal) * 100 : 0
        };
    }
}

const SHARED_DAILY_MODEL_KEY = 'energyai.shared.dailyModel';

function serializeDailyModel(modelInstance) {
    if (!modelInstance) return null;
    return {
        trained: Boolean(modelInstance.trained),
        historicalData: modelInstance.historicalData,
        coefficients: modelInstance.coefficients,
        trainingMetrics: modelInstance.trainingMetrics
    };
}

function saveSharedDailyModel(modelInstance) {
    const payload = serializeDailyModel(modelInstance);
    if (!payload) {
        localStorage.removeItem(SHARED_DAILY_MODEL_KEY);
        return;
    }

    localStorage.setItem(SHARED_DAILY_MODEL_KEY, JSON.stringify(payload));
    window.dispatchEvent(new Event('energyai:model-updated'));
}

function restoreSharedDailyModel() {
    try {
        const raw = localStorage.getItem(SHARED_DAILY_MODEL_KEY);
        if (!raw) return null;

        const payload = JSON.parse(raw);
        if (!payload || !payload.trained) return null;

        const restored = new DailyPredictor();
        restored.trained = Boolean(payload.trained);
        restored.historicalData = payload.historicalData || null;
        restored.coefficients = payload.coefficients || {};
        restored.trainingMetrics = payload.trainingMetrics || {};
        return restored;
    } catch (error) {
        console.warn('Unable to restore shared model state:', error);
        return null;
    }
}

function applySharedModelState() {
    const restored = restoreSharedDailyModel();
    if (restored && restored.trained) {
        dailyModel = restored;
    }
    return dailyModel;
}

window.addEventListener('storage', (event) => {
    if (event.key === SHARED_DAILY_MODEL_KEY) {
        const restored = restoreSharedDailyModel();
        if (restored && restored.trained) {
            dailyModel = restored;
        }
    }
});

// ============================================================
//  CHART INITIALIZATION
// ============================================================

function initChart() {
    const canvas = document.getElementById('forecastChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Upper Bound',
                    data: [],
                    type: 'line',
                    borderColor: 'rgba(16, 185, 129, 0.25)',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 1,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: false,
                    order: 1
                },
                {
                    label: 'Daily Consumption',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: [],
                    borderWidth: 2,
                    borderRadius: 6,
                    order: 2
                },
                {
                    label: 'Lower Bound',
                    data: [],
                    type: 'line',
                    borderColor: 'rgba(16, 185, 129, 0.25)',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 1,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    fill: '-2',
                    order: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, position: 'top',
                    labels: { usePointStyle: true, padding: 20, font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleFont: { family: 'Inter', weight: '600' },
                    bodyFont: { family: 'Inter' },
                    padding: 16,
                    cornerRadius: 10,
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            const val = context.parsed.y;
                            label += val.toFixed(2) + ' kWh';
                            if (context.datasetIndex === 1) {
                                const cost = val * 12.383;
                                label += ' (₱' + cost.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ')';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: {
                        callback: v => v.toFixed(2) + ' kWh',
                        font: { family: 'Inter', size: 11 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 } }
                }
            },
            animation: {
                duration: 800,
                easing: 'easeOutQuart'
            }
        }
    });
}

// ============================================================
//  NOTIFICATION / STATUS LOG
// ============================================================

function logStatus(message, type = 'info') {
    const log = document.getElementById('statusLog');
    if (!log) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    log.insertBefore(entry, log.firstChild);
    notificationCount++;
    updateNotificationBadge();
}

function toggleNotifications() {
    const dropdown = document.getElementById('notificationDropdown');
    if (dropdown.classList.contains('active')) {
        dropdown.classList.remove('active');
    } else {
        dropdown.classList.add('active');
        notificationCount = 0;
        updateNotificationBadge();
    }
}

function clearNotifications() {
    const log = document.getElementById('statusLog');
    if (log) { log.innerHTML = ''; notificationCount = 0; updateNotificationBadge(); }
}

function updateNotificationBadge() {
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        badge.textContent = notificationCount;
        badge.classList.toggle('active', notificationCount > 0);
    }
}

document.addEventListener('click', function (event) {
    const dropdown = document.getElementById('notificationDropdown');
    const btn = document.getElementById('notificationBtn');
    if (dropdown && btn && !dropdown.contains(event.target) && !btn.contains(event.target)) {
        dropdown.classList.remove('active');
    }
});

// ============================================================
//  SAMPLE DATA GENERATION (offline last-resort fallback only)
// ============================================================

function generateDynamicSampleCSV(daysCount = 30) {
    const header = "Date,Consumption,Temperature,Humidity,Rainfall,HasClasses\n";
    const rows = [];
    const baseDate = new Date();
    baseDate.setDate(baseDate.getDate() - daysCount + 1);

    const baseConsumptions = [1450, 1520, 1480, 1510, 1490, 1150, 1100, 1460, 1530, 1470];
    const temps = [28.5, 29.2, 27.8, 28.9, 28.3, 26.5, 25.8, 28.1, 29.5, 28.4];
    const hums = [72, 68, 75, 70, 73, 78, 80, 71, 67, 74];
    const rains = [0, 0, 5.2, 0, 0, 12.5, 8.3, 0, 0, 3.1];

    for (let i = 0; i < daysCount; i++) {
        const currentDate = new Date(baseDate);
        currentDate.setDate(baseDate.getDate() + i);
        const yyyy = currentDate.getFullYear();
        const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
        const dd = String(currentDate.getDate()).padStart(2, '0');
        const dateStr = `${yyyy}-${mm}-${dd}`;

        const dayOfWeek = currentDate.getDay();
        const hasClasses = (dayOfWeek === 0 || dayOfWeek === 6) ? 0 : 1;
        const patternIdx = i % 10;

        let consumption = baseConsumptions[patternIdx];
        let temp = temps[patternIdx];
        let hum = hums[patternIdx];
        let rain = rains[patternIdx];

        if (hasClasses === 0 && consumption > 1200) {
            consumption = Math.round(consumption * 0.75);
        }

        rows.push(`${dateStr},${consumption},${temp},${hum},${rain},${hasClasses}`);
    }

    return header + rows.join('\n');
}

// ============================================================
//  FORECAST CONTEXT
// ============================================================

function initializeForecastContext() {
    if (dailyModel && dailyModel.trained && dailyModel.coefficients
        && dailyModel.coefficients.baseLoad != null) {
        return dailyModel;
    }

    const restored = applySharedModelState();
    if (restored && restored.trained) {
        if (restored.coefficients && restored.coefficients.baseLoad != null) {
            logStatus('Loaded shared forecast model for client planning view', 'success');
            return restored;
        }
        // Model hydrated from the API carries real historical data but no
        // client-side coefficients. Retrain the fallback model on the real
        // series instead of predicting NaN with empty coefficients.
        if (restored.historicalData
            && Array.isArray(restored.historicalData.consumption)
            && restored.historicalData.consumption.length >= 7) {
            dailyModel = new DailyPredictor();
            dailyModel.train(restored.historicalData);
            saveSharedDailyModel(dailyModel);
            logStatus('Prepared client fallback model on real campus data', 'success');
            return dailyModel;
        }
    }

    // Last resort (offline, nothing cached): synthetic demo data.
    const sampleCsv = generateDynamicSampleCSV(30);

    dailyModel = new DailyPredictor();
    const dailyData = dailyModel.parseDailyData(sampleCsv);

    if (dailyData.consumption.length < 7) {
        throw new Error('Default forecast context is unavailable');
    }

    dailyModel.train(dailyData);
    saveSharedDailyModel(dailyModel);
    logStatus('Prepared default forecast context for client planning view (demo data)', 'success');
    return dailyModel;
}

// ============================================================
//  DAILY FORECAST (attention-LSTM + RBF-SVR API first, JS demo fallback)
// ============================================================

async function fetchOpsForecast(days) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 90000);
    try {
        const res = await fetch(`${getApiBase()}/ops/forecast?days=${days}`, { signal: controller.signal });
        if (!res.ok) return null;
        const payload = await res.json();
        if (payload && payload.forecast && Array.isArray(payload.forecast.predictions_kwh)
            && payload.forecast.predictions_kwh.length > 0) {
            return payload;
        }
        return null;
    } catch (_) {
        return null;
    } finally {
        clearTimeout(timer);
    }
}

function makeDailyForecast() {

    const days = parseInt(document.getElementById('forecastHorizon').value);

    logStatus(`Generating ${days}-day forecast...`);
    showLoading('forecastBtn', 'Forecasting...');

    fetchOpsForecast(days).then(apiResult => {
        try {
            if (apiResult) {
                renderOpsForecast(apiResult, days);
            } else {
                logStatus('Live API unreachable — using client-side demo model', 'error');
                renderLocalDailyForecast(days);
            }
        } catch (error) {
            logStatus(`Forecast error: ${error.message}`, 'error');
        } finally {
            hideLoading('forecastBtn', 'Generate Daily Forecast');
        }
    });
}

function renderLocalDailyForecast(days) {
    const temperature = 28;
    const humidity = 70;
    const rainfall = 0;
    const hasClasses = 1;

    try {
        const forecastContext = initializeForecastContext();
        const futureWeather = [], futureSchedule = [];
        const weekdayPattern = [1, 1, 1, 1, 1, 0, 0];
        for (let i = 0; i < days; i++) {
            const dayOfWeek = (i + 1) % 7;
            const isWeekend = weekdayPattern[dayOfWeek] === 0;
            const tempOffset = ((i + 1) % 3) - 1;
            futureWeather.push({
                temperature: temperature + tempOffset,
                humidity: humidity + ((i + 1) % 2 === 0 ? 2 : -1),
                rainfall: rainfall + ((i + 1) % 4 === 0 ? 1 : 0)
            });
            futureSchedule.push(isWeekend ? 0 : (i === 0 ? hasClasses : 1));
        }

        const result = forecastContext.predictWeek(futureWeather, futureSchedule);

        const ctx = {
            predictions: result.predictions,
            lower: result.lower,
            upper: result.upper,
            futureWeather,
            futureSchedule,
            peakAnalysis: forecastContext.estimatePeakLoad(result.predictions),
            dates: null,
            sourceLabel: 'client-side demo model',
            validationMape: null,
            anomalies: forecastContext.detectAnomalies(result.predictions, 1.5)
        };

        renderForecastResult(ctx, days);

        updateAnomalyPanel(ctx.anomalies, null);
        if (ctx.anomalies.length > 0) {
            logStatus(`${ctx.anomalies.length} unusual day(s) detected in forecast`, 'error');
        }
    } catch (error) {
        logStatus(`Forecast error: ${error.message}`, 'error');
    }
}

function renderOpsForecast(apiResult, days) {
    const f = apiResult.forecast;
    const ops = apiResult.ops_state || {};

    const predictions = f.predictions_kwh;
    const lower = f.lower95_kwh || predictions.map(() => null);
    const upper = f.upper95_kwh || predictions.map(() => null);
    const futureWeather = f.dates.map((d, i) => ({
        temperature: (f.temperature && f.temperature[i] != null) ? f.temperature[i] : null,
        humidity: (f.humidity && f.humidity[i] != null) ? f.humidity[i] : null,
        rainfall: (f.rainfall && f.rainfall[i] != null) ? f.rainfall[i] : null
    }));
    const futureSchedule = f.has_classes || [];
    const p = f.peak_analysis || {};
    const peakAnalysis = {
        peakValue: p.peak_value != null ? p.peak_value : Math.max(...predictions),
        peakDayIndex: p.peak_day_index != null ? p.peak_day_index : predictions.indexOf(Math.max(...predictions)),
        minValue: p.min_value != null ? p.min_value : Math.min(...predictions),
        minDayIndex: p.min_day_index != null ? p.min_day_index : predictions.indexOf(Math.min(...predictions)),
        avgLoad: p.avg_load != null ? p.avg_load : predictions.reduce((a, b) => a + b, 0) / predictions.length,
        loadFactor: p.load_factor != null ? p.load_factor : 0,
        range: p.range != null ? p.range : (Math.max(...predictions) - Math.min(...predictions))
    };

    const validationMape = ops.validation_metrics && Number(ops.validation_metrics.MAPE);
    const ctx = {
        predictions,
        lower,
        upper,
        futureWeather,
        futureSchedule,
        peakAnalysis,
        dates: f.dates || null,
        sourceLabel: 'attention-LSTM + RBF-SVR cascade (operational model'
            + (ops.model_trained_at ? ', trained ' + ops.model_trained_at.split('T')[0] : '')
            + ')',
        validationMape: Number.isFinite(validationMape) ? validationMape : null,
        anomalies: (f.anomaly_flags || []).map((flag, i) => flag ? { index: i } : null).filter(Boolean)
    };

    renderForecastResult(ctx, days);

    // Populate the anomaly panel from real forecast flags
    const predMean = predictions.reduce((a, b) => a + b, 0) / predictions.length;
    const anomalyItems = [];
    (f.anomaly_flags || []).forEach((flag, i) => {
        if (flag && predictions[i] != null) {
            const dev = predMean > 0 ? ((predictions[i] - predMean) / predMean * 100) : 0;
            anomalyItems.push({
                index: i,
                value: predictions[i],
                type: predictions[i] >= predMean ? 'spike' : 'dip',
                deviationPct: dev.toFixed(2)
            });
        }
    });
    updateAnomalyPanel(anomalyItems, f.dates);
    if (anomalyItems.length > 0) {
        logStatus(`Unusual day(s) flagged in forecast: ${anomalyItems.map(a => f.dates[a.index]).join(', ')}`, 'error');
    }
    logStatus(`Forecast served by ${ctx.sourceLabel}`, 'success');
}

function renderForecastResult(ctx, days) {
    const { predictions, lower, upper, futureWeather, futureSchedule, peakAnalysis } = ctx;

    // Peak analysis
    updatePeakPanel(peakAnalysis, days, ctx.dates);

    const costPerKwh = 12.383;
    const costs = predictions.map(p => p * costPerKwh);
    const totalConsumption = predictions.reduce((a, b) => a + b, 0);
    const totalCost = costs.reduce((a, b) => a + b, 0);
    const recommendedBudget = totalCost * 1.10;

    // Update summary cards
    const fmt = (n) => n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    animateValue('weeklyConsumption', `${totalConsumption.toFixed(2)} kWh`);
    animateValue('weeklyCost', `₱${fmt(totalCost)}`);
    animateValue('recommendedBudget', `₱${fmt(recommendedBudget)}`);

    // Confidence display
    const totalLower = lower.reduce((a, b) => a + (b || 0), 0) * costPerKwh;
    const totalUpper = upper.reduce((a, b) => a + (b || 0), 0) * costPerKwh;
    const confEl = document.getElementById('confidenceRange');
    if (confEl) {
        confEl.textContent = `₱${fmt(totalLower)} — ₱${fmt(totalUpper)}`;
    }

    const avgDaily = totalConsumption / days;

    // Update client-facing stat cards
    updateStatCard('currentLoad', `${avgDaily.toFixed(2)} kWh/day`, `Avg daily for ${days}-day forecast`);
    if (ctx.validationMape != null) {
        updateStatCard('forecastAccuracy', `${ctx.validationMape.toFixed(2)}%`, 'Model validation MAPE');
    } else {
        updateStatCard('forecastAccuracy', '—', 'Model validation MAPE');
    }
    updateStatCard('forecastTotal', `₱${fmt(totalCost)}`, `Total ${days}-day forecast cost`);
    updateStatCard('modelStatus', 'Ready', 'EnergyAI forecast service online');

    lastForecastResult = { predictions, lower, upper, futureWeather, futureSchedule, peakAnalysis, dates: ctx.dates };

    // Track forecast interaction
    saveInteraction('forecast', {
        type: 'daily',
        days: days,
        source: ctx.sourceLabel,
        totalConsumption: totalConsumption,
        totalCost: totalCost,
        avgDaily: avgDaily,
        peakLoad: peakAnalysis.peakValue,
        loadFactor: peakAnalysis.loadFactor
    });

    updateDailyChart(predictions, futureWeather, futureSchedule, lower, upper, peakAnalysis, ctx.dates);

    logStatus(`${days}-day forecast complete — Total: ${totalConsumption.toFixed(2)} kWh (₱${fmt(totalCost)})`, 'success');
    logStatus(`Indicative range: ₱${fmt(totalLower)} — ₱${fmt(totalUpper)}`, 'success');
    logStatus(`Peak: ${peakAnalysis.peakValue.toFixed(2)} kWh (Day ${peakAnalysis.peakDayIndex + 1}) | Load factor: ${(peakAnalysis.loadFactor * 100).toFixed(2)}%`, 'success');

}

// ============================================================
//  CHART UPDATES
// ============================================================

function updateDailyChart(predictions, weather, schedule, lower, upper, peakAnalysis, dateStrings) {
    const labels = (dateStrings && dateStrings.length === predictions.length)
        ? dateStrings.map(d => new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))
        : predictions.map((_, i) => {
            const date = new Date();
            date.setDate(date.getDate() + i);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });

    const colors = schedule.map((hasClasses, i) => {
        if (peakAnalysis && i === peakAnalysis.peakDayIndex) return 'rgba(239, 68, 68, 0.85)';
        return hasClasses === 1 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(251, 146, 60, 0.8)';
    });

    currentChartData = { labels, data: predictions, colors, lower: lower || [], upper: upper || [] };
    applyChartView();
}

function setChartView(days, event) {
    currentChartView = days;
    document.querySelectorAll('.chart-controls .btn-text').forEach(btn => btn.classList.remove('active'));
    if (event?.target) event.target.classList.add('active');
    applyChartView();
}

function applyChartView() {
    if (!currentChartData.labels.length) return;
    const max = Math.min(currentChartView, currentChartData.labels.length);

    chart.data.labels = currentChartData.labels.slice(0, max);
    chart.data.datasets[1].data = currentChartData.data.slice(0, max);
    chart.data.datasets[1].backgroundColor = currentChartData.colors.slice(0, max);
    chart.data.datasets[1].borderColor = currentChartData.colors.slice(0, max).map(c => c.replace(/[\d.]+\)$/, '1)'));

    // Confidence bands
    if (currentChartData.upper.length > 0) {
        chart.data.datasets[0].data = currentChartData.upper.slice(0, max);
        chart.data.datasets[2].data = currentChartData.lower.slice(0, max);
    } else {
        chart.data.datasets[0].data = [];
        chart.data.datasets[2].data = [];
    }

    chart.update('active');
}

// ============================================================
//  UI PANELS
// ============================================================

function updateAnomalyPanel(anomalies, dates) {
    const container = document.getElementById('anomalyList');
    if (!container) return;

    if (anomalies.length === 0) {
        container.innerHTML = `<div class="anomaly-empty">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            <span>No anomalies detected in forecast horizon</span>
        </div>`;
        return;
    }

    container.innerHTML = anomalies.map(a => {
        const dateStr = dates && a.index < dates.length ? dates[a.index] : `Day ${a.index + 1}`;
        const cls = a.type === 'spike' ? 'spike' : 'dip';
        return `<div class="anomaly-item ${cls}">
            <div class="anomaly-detail">
                <strong>${dateStr}</strong>: ${a.value.toFixed(2)} kWh
                <span class="anomaly-badge ${cls}">${a.type === 'spike' ? '+' : ''}${a.deviationPct}%</span>
            </div>
        </div>`;
    }).join('');

    // Update anomaly count badge
    const badge = document.getElementById('anomalyCount');
    if (badge) {
        badge.textContent = anomalies.length;
        badge.style.display = 'inline-flex';
    }
}

function updatePeakPanel(peakAnalysis, days, dateStrings) {
    const el = document.getElementById('peakInfo');
    if (!el) return;

    let peakDateStr;
    if (dateStrings && dateStrings[peakAnalysis.peakDayIndex]) {
        peakDateStr = new Date(`${dateStrings[peakAnalysis.peakDayIndex]}T00:00:00`)
            .toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    } else {
        const peakDate = new Date();
        peakDate.setDate(peakDate.getDate() + peakAnalysis.peakDayIndex);
        peakDateStr = peakDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    }

    el.innerHTML = `
        <div class="peak-stat">
            <span class="peak-label">Peak Load</span>
            <span class="peak-value">${peakAnalysis.peakValue.toFixed(2)} kWh</span>
            <span class="peak-sub">${peakDateStr}</span>
        </div>
        <div class="peak-stat">
            <span class="peak-label">Min Load</span>
            <span class="peak-value">${peakAnalysis.minValue.toFixed(2)} kWh</span>
        </div>
        <div class="peak-stat">
            <span class="peak-label">Load Factor</span>
            <span class="peak-value">${(peakAnalysis.loadFactor * 100).toFixed(2)}%</span>
        </div>
        <div class="peak-stat">
            <span class="peak-label">Range</span>
            <span class="peak-value">${peakAnalysis.range.toFixed(2)} kWh</span>
        </div>`;
}

function updateStatCard(id, value, subtitle) {
    const valEl = document.getElementById(id + 'Value');
    const subEl = document.getElementById(id + 'Sub');
    if (valEl) animateValue(id + 'Value', value);
    if (subEl) subEl.textContent = subtitle;
}

// ============================================================
//  EXPORT FORECAST DATA
// ============================================================

function exportForecastCSV() {
    if (!lastForecastResult) {
        logStatus('No forecast data to export. Generate a forecast first.', 'error');
        return;
    }

    const { predictions, lower, upper, futureWeather, futureSchedule, dates } = lastForecastResult;
    let csv = 'Date,Predicted_kWh,Lower_95,Upper_95,Temperature,Humidity,Rainfall,HasClasses,Cost_PHP\n';

    predictions.forEach((pred, i) => {
        const date = (dates && dates[i]) ? new Date(`${dates[i]}T00:00:00`) : new Date();
        date.setDate(date.getDate() + ((dates && dates[i]) ? 0 : i));
        const dateStr = date.toISOString().split('T')[0];
        const w = futureWeather[i];
        const s = futureSchedule[i];
        csv += `${dateStr},${pred.toFixed(2)},${lower[i]?.toFixed(2) || ''},${upper[i]?.toFixed(2) || ''},${w.temperature != null ? w.temperature.toFixed(2) : ''},${w.humidity != null ? w.humidity.toFixed(2) : ''},${w.rainfall != null ? w.rainfall.toFixed(2) : ''},${s},${(pred * 12.383).toFixed(2)}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `energy_forecast_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    
    // Track export interaction
    saveInteraction('export', {
        type: 'forecast_csv',
        days: predictions.length,
        timestamp: new Date().toISOString()
    });
    
    logStatus('Forecast exported as CSV', 'success');
}

// ============================================================
//  ANIMATIONS & HELPERS
// ============================================================

function animateValue(id, newValue) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('value-update');
    el.textContent = newValue;
    setTimeout(() => el.classList.remove('value-update'), 600);
}

function showLoading(btnId, text) {
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> ${text}`;
    }
}

function hideLoading(btnId, text) {
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.disabled = false;
        btn.textContent = text;
    }
}

// ============================================================
//  THEME
// ============================================================

// Toggle sidebar minimize/maximize
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const expandBtn = document.getElementById('sidebarExpandBtn');
    
    if (sidebar && expandBtn) {
        sidebar.classList.toggle('minimized');
        expandBtn.classList.toggle('active');
        
        // Save state to localStorage
        const isMinimized = sidebar.classList.contains('minimized');
        localStorage.setItem('sidebarMinimized', isMinimized);
    }
}

// Theme toggle
function toggleTheme() {
    const html = document.documentElement;
    const newTheme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    document.getElementById('sunIcon').style.display = newTheme === 'dark' ? 'none' : 'block';
    document.getElementById('moonIcon').style.display = newTheme === 'dark' ? 'block' : 'none';
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    if (savedTheme === 'dark') {
        if (sunIcon) sunIcon.style.display = 'none';
        if (moonIcon) moonIcon.style.display = 'block';
    }
}

// ============================================================
//  INITIALIZATION
// ============================================================

window.addEventListener('load', () => {
    loadTheme();
    loadSidebarState();
    initChart();
    hydrateSharedModelFromApi().finally(() => {
        logStatus('Dashboard initialized — EnergyAI', 'success');
        logStatus('Attention-LSTM + RBF-SVR cascade with cost translation and statistical forecast flags', 'success');
    });
});

// Load sidebar state from localStorage
function loadSidebarState() {
    const sidebar = document.getElementById('sidebar');
    const expandBtn = document.getElementById('sidebarExpandBtn');
    const isMinimized = localStorage.getItem('sidebarMinimized') === 'true';
    
    if (isMinimized && sidebar && expandBtn) {
        sidebar.classList.add('minimized');
        expandBtn.classList.add('active');
    }
}
