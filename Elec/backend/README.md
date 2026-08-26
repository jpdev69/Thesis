# Backend (Thesis-Critical)

FastAPI backend for hybrid forecasting and ARIMA baseline benchmarking.

## Main Service

- Entry file: `daily_api.py`
- Start command:
  - `python daily_api.py`

## Thesis Endpoints

- `POST /train-daily`
  - Trains the hybrid model from consumption + weather + schedule arrays.
  - Requires at least 30 aligned daily records.
  - Also computes and stores hybrid-vs-ARIMA comparison on validation horizon.

- `POST /forecast-daily`
  - Runs recursive multi-day forecasting (default 7 days).
  - Returns predictions, confidence bounds, anomaly flags, and cost analytics.

- `POST /benchmark-arima`
  - Runs ARIMA holdout benchmark from consumption-only series.

- `GET /baseline-comparison`
  - Returns latest hybrid-vs-ARIMA comparison generated at training time.

- `GET /model-status`
- `GET /metrics`
- `GET /health`

## Notes

- This backend now directly supports all thesis objectives, including objective 2 (ARIMA baseline comparison).
- Runtime evidence is included in API responses (`runtime.uses_tensorflow_lstm`, `runtime.lstm_backend`).
