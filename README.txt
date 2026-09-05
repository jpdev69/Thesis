================================================================================
           ENERGYAI: CAMPUS ELECTRICITY DEMAND FORECASTING SYSTEM
   Hybrid Attention-LSTM + RBF-SVR Architecture for ISU Echague Campus
================================================================================

1. QUICK START (RUNNING THE SYSTEM)
--------------------------------------------------------------------------------
Step 1: Start the Backend API (FastAPI)
    python Elec/backend/daily_api.py
    (Runs at http://localhost:8000 by default)

Step 2: Start the Frontend Web Dashboard
    python -m http.server 8080 --directory Elec/frontend

Step 3: Open in Browser
    http://localhost:8080/ (or http://localhost:8080/dashboard.html)


2. DAILY OPERATIONAL UPDATES & MODEL RETRAINING
--------------------------------------------------------------------------------
Run the automated daily update workflow to re-anchor ISELCO bills, fetch ERA5 
weather data, rebuild datasets, and produce 7-day operational forecasts:

    python Elec/examples/daily_update.py [--xlsx path/to/ISUE_ISELCO_Monitoring.xlsx]


3. RESEARCH EXPERIMENTS & BENCHMARKS
--------------------------------------------------------------------------------
- Ablation Study (Thesis Objective 3):
    python Elec/examples/ablation_study.py

- Train Canonical Daily Model:
    python Elec/examples/train_daily_canonical.py

- Evaluated Rolling Forecast (7-day):
    python Elec/examples/evaluate_rolling_7day.py


4. REPOSITORY STRUCTURE
--------------------------------------------------------------------------------
Elec/
├── backend/            FastAPI server (daily_api.py) & REST endpoints
├── frontend/           Web dashboard, analytics, model catalog, reports
├── src/                Core thesis source code
│   ├── data/           ISELCO bill parser, Denton disaggregations, weather client
│   ├── models/         DailyEnergyPredictor (Hybrid Attention-LSTM + RBF-SVR) & ARIMA
│   └── evaluation/     Metrics calculations, daily & monthly benchmarks
├── examples/           Active operational and research scripts
│   └── prototype/      Standalone developer tutorials and early prototypes
└── data/               Canonical thesis datasets & ISELCO templates
================================================================================
