# Frontend (Thesis-Critical)

This frontend provides the thesis demonstration interface for forecasting outputs and model evaluation.

## Run

Use any static server from the `Elec` directory, for example:

```bash
python -m http.server 8080 --directory frontend
```

Open: `http://localhost:8080`

Run backend API on default thesis port:

```bash
python backend/daily_api.py
```

API default endpoint: `http://localhost:8000`

## Thesis-Relevant Pages

- `models.html` - technical model training metrics and baseline comparison table (includes ARIMA baseline row when backend is running).
- `dashboard.html` - operational forecast outputs and cost-oriented display.

## Notes

- Keep this layer focused on thesis evidence: metrics, forecast plots, baseline comparisons, and decision-support outputs.
- Frontend API base URL is configurable in `settings.html` and stored in localStorage key `energyai.apiBase`.
