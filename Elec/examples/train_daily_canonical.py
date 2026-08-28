"""Train the hybrid LSTM-SVM on the canonical daily dataset.

Executes the multivariate training plan:
- chronological 85/15 split (train+validation block, locked holdout)
- hybrid LSTM-SVM training (attention LSTM -> SVM cascade)
- recursive multi-step forecast on the locked holdout
- ARIMA baseline benchmark on the same split
- 7-day sample forecast beyond the dataset (demonstration output)

Outputs:
1) data/processed/hybrid_vs_arima_test_metrics.csv
2) data/processed/7day_recursive_forecast_samples.csv
3) docs/daily_training_results.md
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data.build_daily_canonical import has_classes_on
from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline
from src.models.daily_prediction_model import DailyEnergyPredictor

HOLDOUT_RATIO = 0.85
EPOCHS = 100
THESIS_TARGETS = {"MAPE": 8.0, "R2": 0.85}


def load_canonical() -> pd.DataFrame:
    csv = ROOT / "data" / "daily_canonical_dataset.csv"
    df = pd.read_csv(csv, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def arrays(df: pd.DataFrame) -> dict:
    return {
        "consumption": df["Consumption"].to_numpy(float),
        "temperature": df["Temperature"].to_numpy(float),
        "humidity": df["Humidity"].to_numpy(float),
        "rainfall": df["Rainfall"].to_numpy(float),
        "has_classes": df["HasClasses"].to_numpy(int),
        "day_of_week": df["DayOfWeek"].to_numpy(int),
        "is_weekend": df["IsWeekend"].to_numpy(int),
    }


def main():
    df = load_canonical()
    n = len(df)
    split_idx = int(n * HOLDOUT_RATIO)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    print(f"Dataset: {n} days | train block: {len(train_df)} | holdout: {len(test_df)}")

    train = arrays(train_df)
    test = arrays(test_df)
    train_dates = train_df["Date"].dt.strftime("%Y-%m-%d").tolist()

    model = DailyEnergyPredictor(sequence_length=7)
    model.train(
        consumption=train["consumption"],
        temperature=train["temperature"],
        humidity=train["humidity"],
        rainfall=train["rainfall"],
        has_classes=train["has_classes"],
        day_of_week=train["day_of_week"],
        is_weekend=train["is_weekend"],
        dates=train_dates,
        epochs=EPOCHS,
        validation_split=0.2,
    )

    past = {k: v[-7:] for k, v in train.items()}
    holdout = model.predict_next_n_days(
        past,
        {"temperature": test["temperature"], "humidity": test["humidity"], "rainfall": test["rainfall"]},
        {"has_classes": test["has_classes"], "day_of_week": test["day_of_week"], "is_weekend": test["is_weekend"]},
        n_days=len(test_df),
    )
    hybrid_preds = np.asarray(holdout["predictions"], dtype=float)
    hybrid_metrics = ForecastingMetrics.calculate_all_metrics(test["consumption"], hybrid_preds)

    arima = ARIMABaseline()
    arima_eval = arima.evaluate(train["consumption"], test["consumption"])
    arima_metrics = arima_eval["metrics"]

    print("\n=== Locked holdout comparison (recursive multi-step) ===")
    print(f"{'Metric':6} {'Hybrid':>12} {'ARIMA':>12}")
    for m in ["RMSE", "MAE", "MAPE", "R2"]:
        print(f"{m:6} {hybrid_metrics[m]:>12.3f} {arima_metrics[m]:>12.3f}")

    metrics_df = pd.DataFrame([
        {"model": "Hybrid_LSTM_SVM", **{k: float(hybrid_metrics[k]) for k in ["RMSE", "MAE", "MAPE", "R2"]}},
        {"model": "ARIMA", **{k: float(arima_metrics[k]) for k in ["RMSE", "MAE", "MAPE", "R2"]}},
    ])
    metrics_path = ROOT / "data" / "processed" / "hybrid_vs_arima_test_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\nSaved {metrics_path}")

    full = arrays(df)
    future_dates = [df['Date'].iloc[-1] + timedelta(days=i) for i in range(1, 8)]
    future = {
        "temperature": np.repeat(df['Temperature'].iloc[-7:].mean(), 7),
        "humidity": np.repeat(df['Humidity'].iloc[-7:].mean(), 7),
        "rainfall": np.repeat(df['Rainfall'].iloc[-7:].mean(), 7),
    }
    future_schedule = {
        "has_classes": np.array([has_classes_on(d.date()) for d in future_dates]),
        "day_of_week": np.array([d.weekday() for d in future_dates]),
        "is_weekend": np.array([int(d.weekday() >= 5) for d in future_dates]),
    }
    past_all = {k: v[-7:] for k, v in full.items()}
    sample = model.predict_next_n_days(past_all, future, future_schedule, n_days=7)
    sample_df = pd.DataFrame({
        "Date": [d.strftime("%Y-%m-%d") for d in future_dates],
        "PredictedConsumption": np.round(sample["predictions"], 1),
        "Lower95": np.round(sample["lower"], 1),
        "Upper95": np.round(sample["upper"], 1),
        "HasClasses": future_schedule["has_classes"],
        "AssumedTemperature": np.round(future["temperature"], 1),
    })
    sample_path = ROOT / "data" / "processed" / "7day_recursive_forecast_samples.csv"
    sample_df.to_csv(sample_path, index=False)
    print(f"Saved {sample_path}")

    report = [
        "# Daily Training Results (Canonical Multivariate Dataset)",
        "",
        f"Run: {datetime.now().isoformat(timespec='seconds')}",
        f"Dataset: {n} days ({df['Date'].iloc[0].date()} to {df['Date'].iloc[-1].date()})",
        f"Split: chronological {HOLDOUT_RATIO:.0%} train block / {1 - HOLDOUT_RATIO:.0%} locked holdout",
        f"Epochs: {EPOCHS} (early stopping active), sequence length 7",
        "",
        "## Locked Holdout Metrics (recursive multi-step)",
        "",
        "| Model | RMSE | MAE | MAPE | R2 |",
        "|---|---:|---:|---:|---:|",
        f"| Hybrid LSTM-SVM | {hybrid_metrics['RMSE']:.2f} | {hybrid_metrics['MAE']:.2f} | {hybrid_metrics['MAPE']:.2f} | {hybrid_metrics['R2']:.4f} |",
        f"| ARIMA | {arima_metrics['RMSE']:.2f} | {arima_metrics['MAE']:.2f} | {arima_metrics['MAPE']:.2f} | {arima_metrics['R2']:.4f} |",
        "",
        f"ARIMA order: {arima_eval['order']} (fallback: {arima_eval['used_fallback']})",
        "",
        "## Thesis Target Check",
        "",
        f"- MAPE target < {THESIS_TARGETS['MAPE']}%: "
        f"{'PASS' if hybrid_metrics['MAPE'] < THESIS_TARGETS['MAPE'] else 'NOT MET'} "
        f"(hybrid {hybrid_metrics['MAPE']:.2f}%)",
        f"- R2 target >= {THESIS_TARGETS['R2']}: "
        f"{'PASS' if hybrid_metrics['R2'] >= THESIS_TARGETS['R2'] else 'NOT MET'} "
        f"(hybrid {hybrid_metrics['R2']:.4f})",
        "",
        "## Notes",
        "",
        "- Consumption target is coverage-adjusted disaggregated daily kWh",
        "  (see docs/daily_data_quality_report.md for method and limitations).",
        "- Holdout evaluation is recursive multi-step over the full holdout;",
        "  short-horizon (7-day rolling) evaluation is reported separately",
        "  by the training validation metrics.",
        "- 7-day demonstration forecast: data/processed/7day_recursive_forecast_samples.csv",
    ]
    report_path = ROOT / "docs" / "daily_training_results.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Saved {report_path}")


if __name__ == "__main__":
    main()
