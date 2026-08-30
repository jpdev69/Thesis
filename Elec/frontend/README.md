# Frontend (Thesis-Critical)

This frontend provides the thesis demonstration interface for forecasting outputs and model evaluation.

## Run

Use any static server from the `Elec` directory, for example:

```bash
python -m http.server 8080 --directory frontend
```

Open: `http://localhost:8080`

The public `index.html` landing page is the default entry. Users continue to
`login.html` only when they explicitly sign in or request access. If an
unauthenticated visitor opens a protected workspace page, the auth guard
returns them to the public landing page.

Run backend API on default thesis port:

```bash
python backend/daily_api.py
```

API default endpoint: `http://localhost:8000`

## Thesis-Relevant Pages

- `index.html` - public landing page with verified capabilities, evaluation
  results, and stated data limitations.
- `login.html` - explicit sign-in and account-request page.
- `models.html` - technical model training metrics and baseline comparison table (includes ARIMA baseline row when backend is running).
- `dashboard.html` - operational forecast outputs and cost-oriented display.

## Notes

- Keep this layer focused on thesis evidence: metrics, forecast plots, baseline comparisons, and decision-support outputs.
- Frontend API base URL is configurable in `settings.html` and stored in localStorage key `energyai.apiBase`.
