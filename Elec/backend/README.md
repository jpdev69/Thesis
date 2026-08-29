# Backend (Thesis-Critical)

FastAPI backend for hybrid forecasting and ARIMA baseline benchmarking.

## Main Service

- Entry file: `daily_api.py`
- Start command:
  - `python daily_api.py`

## Operational Integration

On startup the API auto-loads the operational model trained by
`examples/daily_update.py` (`models/ops/daily/`), so all endpoints serve
the continuously-retrained hybrid LSTM-SVM without in-browser retraining.

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
  - Returns latest hybrid-vs-ARIMA comparison (in-memory training run, or
    live evaluation of the operational model on the current anchored data).

- `GET /ops/forecast?days=N&refresh=true`
  - Latest operational forecast from the daily pipeline.
  - Stored artifact by default, trimmed to the requested horizon;
    longer horizons or `refresh=true` recompute live (ops model + ops
    dataset + current Open-Meteo weather forecast).

- `GET /model-status`
- `GET /metrics`
- `GET /health`

## Notes

- This backend now directly supports all thesis objectives, including objective 2 (ARIMA baseline comparison).
- Runtime evidence is included in API responses (`runtime.uses_tensorflow_lstm`, `runtime.lstm_backend`).
- Legacy demo services (`app.py`, `simple_app.py`, `test_api.py`) were removed;
  `daily_api.py` is the single backend.
