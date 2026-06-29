# Frontend Dashboard

Interactive web dashboard for the Campus Energy Forecasting System.

## Setup

No build step required - pure HTML/CSS/JavaScript.

## Run

1. Start the backend API first (see backend/README.md)

2. Open `index.html` in a web browser, or serve with a local server:

```bash
# Python
python -m http.server 3000

# Node.js
npx http-server -p 3000
```

3. Navigate to `http://localhost:3000`

## Features

- Generate or input energy consumption data
- Train the hybrid LSTM-SVM model
- View performance metrics (RMSE, MAE, MAPE, R²)
- Generate multi-step forecasts
- Interactive visualization with Chart.js
- Real-time status logging
