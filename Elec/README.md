# EnergyAI Thesis Implementation

This folder is the implementation package for the thesis:
"EnergyAI: Development and Evaluation of Campus Energy Forecasting Through Enhanced LSTM and SVM Frameworks."

The documentation here is intentionally minimal and objective-driven.

## Thesis Objectives: Completion Matrix

1. Build cascaded LSTM -> SVM forecasting architecture.
   - Status: Completed.
   - Evidence: `src/models/daily_prediction_model.py`, `src/models/hybrid_model.py`.

2. Compare against classical baseline (ARIMA).
   - Status: Completed.
   - Evidence:
     - ARIMA baseline implementation: `src/models/arima_baseline.py`
     - Hybrid vs ARIMA benchmark utility: `src/evaluation/thesis_benchmark.py`
     - API endpoints: `backend/daily_api.py` (`/benchmark-arima`, `/baseline-comparison`)
     - Frontend comparison row: `frontend/models.html`

3. Integrate exogenous weather variables (temperature, humidity, rainfall).
   - Status: Completed.
   - Evidence: model features + API inputs + forecasting flow.

4. Integrate institutional schedule awareness and prescriptive advisories.
   - Status: Completed.
   - Evidence: schedule-aware features (`has_classes`, `is_weekend`, day-of-week) and cost/advisory outputs in dashboard flow.

5. Validate rolling 7-day performance with RMSE, MAE, MAPE, R2 targets.
   - Status: Completed.
   - Evidence: recursive forecast pipeline and evaluation metrics in model/API/UI.

## Thesis-Critical Files

- `src/models/daily_prediction_model.py` - primary hybrid training and recursive forecasting.
- `src/models/hybrid_model.py` - integrated hybrid architecture variant.
- `src/models/arima_baseline.py` - classical ARIMA baseline.
- `src/evaluation/metrics.py` - evaluation metrics.
- `src/evaluation/thesis_benchmark.py` - objective-2 benchmark helper.
- `backend/daily_api.py` - train/forecast/benchmark API.
- `frontend/models.html` - model metrics and baseline comparison.
- `frontend/dashboard-fixed.js` - cost and advisory display flow.
- `ARCHITECTURE.md` - implementation architecture outline.
- `THESIS_OBJECTIVE_OUTLINE.md` - final objective-to-evidence checklist.

## Minimal Thesis Validation Workflow

1. Install dependencies:
   - `python -m pip install -r requirements.txt`

2. Run API:
   - `python backend/daily_api.py`

3. Train model:
   - `POST /train-daily`

4. Verify benchmark objective (ARIMA):
   - `GET /baseline-comparison` (hybrid vs ARIMA after training)
   - or run `POST /benchmark-arima` directly.

5. Generate 7-day forecast:
   - `POST /forecast-daily`

6. Confirm thesis metrics and table in frontend:
   - `frontend/models.html`

## Documentation Policy

Only thesis-essential documentation is retained. New docs should directly support objectives, experiments, or final defense evidence.
