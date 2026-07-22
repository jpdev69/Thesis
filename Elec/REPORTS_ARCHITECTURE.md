# Reports System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         EnergyAI System                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│   Dashboard Page     │         │    Reports Page      │
│  dashboard-fixed.js  │◄───────►│     reports.js       │
└──────────────────────┘         └──────────────────────┘
         │                                  │
         │                                  │
         ├─ Train Model ───────┐            │
         ├─ Generate Forecast ─┤            │
         └─ Export Data ────────┤            │
                               │            │
                               ▼            ▼
                      ┌────────────────────────┐
                      │   localStorage API     │
                      ├────────────────────────┤
                      │ interactionHistory     │
                      │ scheduledReports       │
                      │ shared.dailyModel      │
                      └────────────────────────┘
```

## Data Flow Diagram

### Training Interaction Flow
```
User clicks "Train Model"
        ↓
trainDailyModel() / trainModel()
        ↓
Model training completes
        ↓
saveInteraction('training', {...})
        ↓
Store in localStorage
        ↓
Reports page reads on load
        ↓
Display in "Recent Reports"
```

### Forecast Interaction Flow
```
User clicks "Generate Forecast"
        ↓
makeDailyForecast() / makeForecast()
        ↓
Forecast generation completes
        ↓
saveInteraction('forecast', {...})
        ↓
Store in localStorage
        ↓
Reports page reads on load
        ↓
Display in "Recent Reports"
```

## Component Architecture

### Dashboard Component (dashboard-fixed.js)

```javascript
┌─────────────────────────────────────────┐
│      Dashboard-fixed.js                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────┐     │
│  │  Interaction Tracking Layer   │     │
│  │  - saveInteraction()          │     │
│  │  - INTERACTION_HISTORY_KEY    │     │
│  └───────────────────────────────┘     │
│              │                          │
│              │ called by                │
│              ▼                          │
│  ┌───────────────────────────────┐     │
│  │  Training Functions           │     │
│  │  - trainDailyModel()          │     │
│  │  - trainModel()               │     │
│  └───────────────────────────────┘     │
│                                         │
│  ┌───────────────────────────────┐     │
│  │  Forecasting Functions        │     │
│  │  - makeDailyForecast()        │     │
│  │  - makeForecast()             │     │
│  └───────────────────────────────┘     │
│                                         │
│  ┌───────────────────────────────┐     │
│  │  Export Functions             │     │
│  │  - exportForecastCSV()        │     │
│  └───────────────────────────────┘     │
│                                         │
└─────────────────────────────────────────┘
```

### Reports Component (reports.js)

```javascript
┌─────────────────────────────────────────┐
│         Reports.js                      │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────┐     │
│  │  Data Access Layer            │     │
│  │  - getInteractionHistory()    │     │
│  │  - getScheduledReports()      │     │
│  │  - loadSharedForecastState()  │     │
│  └───────────────────────────────┘     │
│              │                          │
│              │ provides data to         │
│              ▼                          │
│  ┌───────────────────────────────┐     │
│  │  Rendering Layer              │     │
│  │  - renderRecentReports()      │     │
│  │  - renderReportTemplates()    │     │
│  │  - renderScheduledReports()   │     │
│  └───────────────────────────────┘     │
│              │                          │
│              │ displays to              │
│              ▼                          │
│  ┌───────────────────────────────┐     │
│  │  UI Layer (DOM)               │     │
│  │  - Recent Reports section     │     │
│  │  - Report Templates section   │     │
│  │  - Scheduled Reports table    │     │
│  └───────────────────────────────┘     │
│              │                          │
│              │ user interactions        │
│              ▼                          │
│  ┌───────────────────────────────┐     │
│  │  Action Layer                 │     │
│  │  - generateReport()           │     │
│  │  - downloadReport()           │     │
│  │  - toggleScheduledReport()    │     │
│  └───────────────────────────────┘     │
│                                         │
└─────────────────────────────────────────┘
```

## Interaction Object Structure

```javascript
{
    id: Number,              // Unique timestamp-based ID
    type: String,            // 'training' | 'forecast' | 'export' | 'report_generation'
    timestamp: String,       // ISO 8601 format: '2026-07-05T10:30:00.000Z'
    data: Object            // Type-specific data
}
```

### Training Interaction Data
```javascript
{
    type: 'training',
    data: {
        type: 'daily' | 'simple',
        dataPoints: Number,
        metrics: {
            RMSE: Number,
            MAE: Number,
            MAPE: Number,
            R2: Number
        },
        classDays?: Number,      // Only for daily
        noClassDays?: Number     // Only for daily
    }
}
```

### Forecast Interaction Data
```javascript
{
    type: 'forecast',
    data: {
        type: 'daily' | 'simple',
        days?: Number,           // For daily
        steps?: Number,          // For simple
        totalConsumption: Number,
        totalCost: Number,
        avgDaily?: Number,       // For daily
        avgPerStep?: Number,     // For simple
        peakLoad?: Number,       // For daily
        loadFactor?: Number      // For daily
    }
}
```

### Export Interaction Data
```javascript
{
    type: 'export',
    data: {
        type: 'forecast_csv',
        days: Number,
        timestamp: String
    }
}
```

## localStorage Schema

### Storage Keys

```javascript
// Key: 'energyai.interactionHistory'
// Type: Array<Interaction>
// Max Size: 50 entries
// Purpose: Store user interaction history
[
    { id: 1720051200000, type: 'training', ... },
    { id: 1720051150000, type: 'forecast', ... },
    // ... up to 50 entries
]

// Key: 'energyai.scheduledReports'
// Type: Array<ScheduledReport>
// Purpose: Store scheduled report configurations
[
    {
        id: 1,
        name: 'Daily Energy Summary',
        frequency: 'Daily at 8:00 AM',
        recipients: 'admin@energy.ai',
        nextRun: 'Tomorrow, 8:00 AM',
        active: true
    },
    // ... more scheduled reports
]

// Key: 'energyai.shared.dailyModel'
// Type: Object
// Purpose: Share trained model data across pages
{
    trained: true,
    historicalData: {
        consumption: [150, 145, 160, ...],
        dates: ['2026-06-01', ...],
        weather: [...],
        schedule: [...]
    },
    trainingMetrics: {
        RMSE: 45.2,
        MAE: 38.7,
        MAPE: 5.2,
        R2: 0.89
    }
}
```

## UI Component Hierarchy

```
reports.html
│
├── Header
│   ├── Title: "Reports"
│   ├── Subtitle: (dynamic from model data)
│   └── Button: "Generate Report" (openReportGenerator)
│
├── Main Content Grid
│   │
│   ├── Card: Recent Reports (grid-column: span 8)
│   │   ├── Header: "Recent Reports"
│   │   └── Body: (rendered by renderRecentReports)
│   │       ├── Empty State (if no interactions)
│   │       └── Report Cards (for each interaction)
│   │           ├── Icon (document SVG)
│   │           ├── Title (from interaction data)
│   │           ├── Metadata (date, size)
│   │           ├── Details (metrics)
│   │           └── Button: "Download PDF"
│   │
│   ├── Card: Report Templates (grid-column: span 4)
│   │   ├── Header: "Report Templates"
│   │   └── Body: (rendered by renderReportTemplates)
│   │       └── Template Buttons (6 templates)
│   │           ├── Icon
│   │           ├── Template Name
│   │           └── Description
│   │
│   └── Card: Scheduled Reports (grid-column: span 12)
│       ├── Header: "Scheduled Reports"
│       └── Body: (rendered by renderScheduledReports)
│           └── Table
│               ├── Columns: Name, Frequency, Recipients, Next Run, Status, Actions
│               └── Rows (for each scheduled report)
```

## Event Flow

### Page Load Sequence
```
1. DOMContentLoaded event fires
        ↓
2. loadTheme()
   - Load saved theme from localStorage
   - Update UI icons
        ↓
3. renderRecentReports()
   - Get interaction history
   - Check if any interactions exist
   - Render report cards or empty state
        ↓
4. renderScheduledReports()
   - Get scheduled reports config
   - Render table rows
        ↓
5. renderReportTemplates()
   - Render template buttons with handlers
        ↓
6. Update subtitle with model info
   - Load shared model state
   - Display data points and avg consumption
```

### Storage Event Listener
```
Another tab/window updates localStorage
        ↓
'storage' event fires
        ↓
Check if key is relevant
(SHARED_DAILY_MODEL_KEY or INTERACTION_HISTORY_KEY)
        ↓
Re-render affected sections
(renderRecentReports)
```

## Integration Points

### 1. Dashboard → Reports
- **Trigger**: User trains model or generates forecast
- **Mechanism**: saveInteraction() writes to localStorage
- **Detection**: Reports page reads on load or storage event

### 2. Reports → Model Data
- **Source**: `energyai.shared.dailyModel`
- **Usage**: Check if model trained, get data for reports
- **Access**: loadSharedForecastState()

### 3. Cross-Tab Communication
- **Mechanism**: localStorage + 'storage' event
- **Benefit**: Live updates across browser tabs
- **Implementation**: Event listener in reports.js

## Security Considerations

```
┌────────────────────────────────────────┐
│         Security Layers                │
├────────────────────────────────────────┤
│                                        │
│  1. Authentication (auth.js)           │
│     - Checks currentUser in localStorage
│     - Redirects to login if not found
│                                        │
│  2. Data Validation                    │
│     - Check interaction type           │
│     - Validate data structure          │
│     - Handle parsing errors            │
│                                        │
│  3. Storage Limits                     │
│     - Max 50 interactions              │
│     - Auto-cleanup old entries         │
│     - Prevent localStorage overflow    │
│                                        │
│  4. XSS Prevention                     │
│     - No innerHTML with user data      │
│     - Use textContent where possible   │
│     - Sanitize display values          │
│                                        │
└────────────────────────────────────────┘
```

## Performance Optimization

### Storage Management
```javascript
// Circular buffer approach
// Always keep last 50 interactions
function saveInteraction(type, data) {
    const history = getInteractionHistory();
    history.unshift(interaction);  // Add to front
    
    if (history.length > 50) {
        history.splice(50);         // Remove excess
    }
    
    localStorage.setItem(key, JSON.stringify(history));
}
```

### Rendering Optimization
```javascript
// Only render visible reports (last 5)
const reportsToShow = reportableInteractions.slice(0, 5);

// Build HTML string (faster than DOM manipulation)
let html = '';
reportsToShow.forEach(interaction => {
    html += `<div>...</div>`;
});
container.innerHTML = html;
```

### Event Debouncing
```javascript
// Prevent excessive re-renders
let renderTimeout;
window.addEventListener('storage', (event) => {
    clearTimeout(renderTimeout);
    renderTimeout = setTimeout(() => {
        renderRecentReports();
    }, 100);
});
```

## Error Handling

```
┌────────────────────────────────────────┐
│        Error Handling Strategy         │
├────────────────────────────────────────┤
│                                        │
│  Try-Catch Blocks                      │
│  - Wrap localStorage access            │
│  - Wrap JSON parsing                   │
│  - Return safe defaults on error       │
│                                        │
│  Graceful Degradation                  │
│  - Show empty state if no data         │
│  - Use placeholder values              │
│  - Log warnings to console             │
│                                        │
│  User Feedback                         │
│  - Alert for missing model data        │
│  - Console warnings for developers     │
│  - Empty state messages for users      │
│                                        │
└────────────────────────────────────────┘
```

---

**Document Version**: 1.0.0  
**Last Updated**: July 5, 2026  
**Purpose**: Technical architecture documentation for Reports System
