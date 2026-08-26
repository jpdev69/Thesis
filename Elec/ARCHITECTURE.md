# EnergyAI Architecture (Thesis-Complete)

## Pipeline Overview

Input -> Preprocessing -> LSTM Feature Extraction -> SVM Regression -> 7-Day Recursive Forecast -> Cost and Advisory Output -> Baseline Benchmarking (ARIMA)

## 1) Inputs

- Endogenous: historical daily campus electricity consumption (kWh).
- Exogenous weather: temperature, humidity, rainfall.
- Institutional schedule: class day, weekend, day-of-week (plus optional holiday marker).

## 2) Preprocessing and Feature Engineering

- Scaling/normalization of continuous variables.
- Cyclical temporal encoding for weekly periodicity.
- 7-day sliding sequence construction for temporal context.

Primary implementation:
- `src/models/daily_prediction_model.py`

## 3) Cascaded Hybrid Core

- Attention-enhanced LSTM extracts temporal representations from multivariate sequences.
- SVM (RBF) consumes stacked features and produces final non-linear prediction.
- Implemented as cascaded integration, not weighted averaging.

Implementation:
- `src/models/daily_prediction_model.py`
- `src/models/hybrid_model.py`

## 4) Forecasting Mode

- Recursive multi-step generation for 7-day look-ahead.
- Day t+1 prediction is fed forward to predict later days.

Implementation:
- `predict_next_n_days(...)` in `src/models/daily_prediction_model.py`

## 5) Evaluation and Targets

- Metrics: RMSE, MAE, MAPE, R2.
- Thesis target thresholds: MAPE < 8%, R2 >= 0.85.

Implementation:
- `src/evaluation/metrics.py`
- training/validation reporting in `src/models/daily_prediction_model.py`

## 6) Classical Baseline Benchmarking (ARIMA)

- ARIMA baseline is implemented for objective-2 comparison.
- Hybrid vs ARIMA comparison is available through API and frontend model catalog flow.

Implementation:
- `src/models/arima_baseline.py`
- `src/evaluation/thesis_benchmark.py`
- `backend/daily_api.py`
- `frontend/models.html`

## 7) API Layer

- `POST /train-daily` - train hybrid model and compute baseline comparison.
- `POST /forecast-daily` - produce n-day recursive forecasts.
- `POST /benchmark-arima` - run ARIMA holdout benchmark.
- `GET /baseline-comparison` - retrieve latest hybrid-vs-ARIMA comparison.
- `GET /model-status`, `GET /health` - system state and health.

Implementation:
- `backend/daily_api.py`
