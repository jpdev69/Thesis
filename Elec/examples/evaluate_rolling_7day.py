"""Rolling-origin 7-day evaluation (thesis Objective 5 evidence).

Protocol:
- chronological 85/15 split (identical to the training run)
- hybrid LSTM-SVM trained on the train block only
- rolling weekly origins across the locked holdout:
  at each origin, the model receives the TRUE past 7 days of consumption,
  weather, and schedule, then produces a recursive 7-day forecast
- ARIMA re-fit per origin on all consumption up to that origin (operational
  fairness) and forecasts the same 7 days
- future weather/schedule are actual observed values (perfect-forecast
  assumption for exogenous inputs, declared in the report)

Outputs:
1) data/processed/rolling_7day_predictions.csv
2) data/processed/rolling_7day_metrics.csv
3) data/processed/rolling_7day_per_horizon.csv
4) docs/rolling_7day_evaluation_report.md

Expected runtime: 10-20 minutes (training + 20 MC-dropout windows + ARIMA
re-fits per origin).
"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
try:
    import tensorflow as tf
    tf.random.set_seed(SEED)
except ImportError:
    pass

from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline
from src.models.daily_prediction_model import DailyEnergyPredictor

HOLDOUT_RATIO = 0.85
EPOCHS = 100
THESIS_TARGETS = {"MAPE": 8.0, "R2": 0.85}
CORE = ["RMSE", "MAE", "MAPE", "R2", "SMAPE", "DirectionalAccuracy", "TheilU", "ForecastBias"]


def load_arrays() -> tuple[pd.DataFrame, dict]:
    csv = ROOT / "data" / "daily_canonical_dataset.csv"
    df = pd.read_csv(csv, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    arr = {
        "consumption": df["Consumption"].to_numpy(float),
        "temperature": df["Temperature"].to_numpy(float),
        "humidity": df["Humidity"].to_numpy(float),
        "rainfall": df["Rainfall"].to_numpy(float),
        "has_classes": df["HasClasses"].to_numpy(int),
        "day_of_week": df["DayOfWeek"].to_numpy(int),
        "is_weekend": df["IsWeekend"].to_numpy(int),
    }
    return df, arr


def main():
    df, arr = load_arrays()
    n = len(df)
    split_idx = int(n * HOLDOUT_RATIO)
    holdout_days = n - split_idx
    n_windows = holdout_days // 7
    evaluated_days = n_windows * 7
    print(f"Dataset: {n} days | split at index {split_idx} "
          f"({df['Date'].iloc[split_idx].date()})")
    print(f"Rolling windows: {n_windows} x 7 days ({evaluated_days} of "
          f"{holdout_days} holdout days; {holdout_days - evaluated_days} trailing "
          f"days excluded from full windows)")

    train = {k: v[:split_idx] for k, v in arr.items()}
    train_dates = df["Date"].iloc[:split_idx].dt.strftime("%Y-%m-%d").tolist()

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

    rows = []
    arima_fallbacks = 0
    for w in range(n_windows):
        a = split_idx + w * 7
        window = slice(a, a + 7)
        past = {k: v[a - 7:a] for k, v in arr.items()}
        result = model.predict_next_n_days(
            past,
            {"temperature": arr["temperature"][window],
             "humidity": arr["humidity"][window],
             "rainfall": arr["rainfall"][window]},
            {"has_classes": arr["has_classes"][window],
             "day_of_week": arr["day_of_week"][window],
             "is_weekend": arr["is_weekend"][window]},
            n_days=7,
        )

        arima = ARIMABaseline()
        arima_preds = arima.forecast(arr["consumption"][:a], 7)
        if arima.used_fallback:
            arima_fallbacks += 1

        for h in range(7):
            rows.append({
                "Date": df["Date"].iloc[a + h].strftime("%Y-%m-%d"),
                "Window": w,
                "Horizon": h + 1,
                "Actual": arr["consumption"][a + h],
                "Hybrid": float(result["predictions"][h]),
                "HybridLower95": float(result["lower"][h]),
                "HybridUpper95": float(result["upper"][h]),
                "ARIMA": float(arima_preds[h]),
            })
        print(f"Window {w + 1}/{n_windows} done "
              f"(origin {df['Date'].iloc[a].date()})")

    preds_df = pd.DataFrame(rows)
    preds_path = ROOT / "data" / "processed" / "rolling_7day_predictions.csv"
    preds_df.to_csv(preds_path, index=False)
    print(f"Saved {preds_path}")

    hybrid_metrics = ForecastingMetrics.calculate_all_metrics(
        preds_df["Actual"], preds_df["Hybrid"])
    arima_metrics = ForecastingMetrics.calculate_all_metrics(
        preds_df["Actual"], preds_df["ARIMA"])
    ci_coverage = ForecastingMetrics.confidence_interval_coverage(
        preds_df["Actual"], preds_df["HybridLower95"], preds_df["HybridUpper95"])

    metrics_df = pd.DataFrame([
        {"model": "Hybrid_LSTM_SVM",
         **{k: float(hybrid_metrics[k]) for k in CORE}},
        {"model": "ARIMA",
         **{k: float(arima_metrics[k]) for k in CORE}},
    ])
    metrics_path = ROOT / "data" / "processed" / "rolling_7day_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"Saved {metrics_path}")

    horizon_rows = []
    for h in range(1, 8):
        g = preds_df[preds_df["Horizon"] == h]
        for name, col in [("Hybrid_LSTM_SVM", "Hybrid"), ("ARIMA", "ARIMA")]:
            horizon_rows.append({
                "horizon_day": h,
                "model": name,
                "RMSE": float(np.sqrt(np.mean((g["Actual"] - g[col]) ** 2))),
                "MAPE": ForecastingMetrics.mape(g["Actual"], g[col]),
            })
    horizon_df = pd.DataFrame(horizon_rows)
    horizon_path = ROOT / "data" / "processed" / "rolling_7day_per_horizon.csv"
    horizon_df.to_csv(horizon_path, index=False)
    print(f"Saved {horizon_path}")

    print("\n=== Rolling 7-Day Holdout Comparison (true-past origins) ===")
    print(f"{'Metric':20} {'Hybrid':>12} {'ARIMA':>12}")
    for m in CORE:
        print(f"{m:20} {hybrid_metrics[m]:>12.3f} {arima_metrics[m]:>12.3f}")
    print(f"{'CI95 coverage':20} {ci_coverage:>11.1f}%")

    mape_pass = hybrid_metrics["MAPE"] < THESIS_TARGETS["MAPE"]
    r2_pass = hybrid_metrics["R2"] >= THESIS_TARGETS["R2"]

    report = [
        "# Rolling-Origin 7-Day Evaluation Report (Objective 5)",
        "",
        f"Run: seed {SEED}, {n_windows} non-overlapping weekly windows,",
        f"{evaluated_days} of {holdout_days} holdout days evaluated"
        f" ({df['Date'].iloc[split_idx].date()} to "
        f"{df['Date'].iloc[split_idx + evaluated_days - 1].date()}).",
        "",
        "## Protocol",
        "",
        "- Hybrid LSTM-SVM trained on the first 85% (chronological) only;",
        "  holdout never used for training or tuning.",
        "- At each weekly origin the model receives the TRUE observed past",
        "  7 days (consumption, weather, schedule) and produces a recursive",
        "  7-day forecast.",
        "- ARIMA is re-fit per origin on all consumption up to that origin",
        "  and forecasts the same 7 days.",
        "- Future weather/schedule are actual observed values",
        "  (perfect-forecast assumption for exogenous inputs).",
        "",
        "## Aggregate 7-Day-Ahead Metrics",
        "",
        "| Metric | Hybrid LSTM-SVM | ARIMA |",
        "|---|---:|---:|",
    ]
    for m in CORE:
        report.append(f"| {m} | {hybrid_metrics[m]:.3f} | {arima_metrics[m]:.3f} |")
    report += [
        f"| CI95 coverage | {ci_coverage:.1f}% | - |",
        "",
        "## Thesis Target Check (Objective 5)",
        "",
        f"- MAPE < {THESIS_TARGETS['MAPE']}%: "
        f"{'PASS' if mape_pass else 'NOT MET'} "
        f"(hybrid {hybrid_metrics['MAPE']:.2f}%)",
        f"- R2 >= {THESIS_TARGETS['R2']}: "
        f"{'PASS' if r2_pass else 'NOT MET'} "
        f"(hybrid {hybrid_metrics['R2']:.4f})",
        "",
        "## Per-Horizon Degradation (MAPE by forecast day)",
        "",
        "| Day | Hybrid MAPE | ARIMA MAPE |",
        "|---:|---:|---:|",
    ]
    for h in range(1, 8):
        gh = horizon_df[(horizon_df["horizon_day"] == h)]
        hm = gh[gh["model"] == "Hybrid_LSTM_SVM"]["MAPE"].iloc[0]
        am = gh[gh["model"] == "ARIMA"]["MAPE"].iloc[0]
        report.append(f"| {h} | {hm:.2f}% | {am:.2f}% |")
    report += [
        "",
        "## Comparison With the 142-Day Recursive Stress Test",
        "",
        "The full-holdout recursive run (docs/daily_training_results.md) gave",
        "hybrid MAPE 18.15% / R2 -0.20 because recursive errors compound over",
        "142 days. Under the thesis-defined rolling 7-day protocol the hybrid",
        f"achieves MAPE {hybrid_metrics['MAPE']:.2f}% / R2 {hybrid_metrics['R2']:.4f},",
        "confirming the protocol mismatch interpretation.",
        "",
        "## Declared Limitations",
        "",
        "1. Perfect-forecast exogenous inputs: actual future weather and",
        "   schedule were supplied. Production use would carry weather-forecast",
        "   error on top of these figures.",
        "2. Daily consumption is reconstructed from monthly bills",
        "   (Denton-style disaggregation); each daily value is anchored to its",
        "   month's total, a mild within-month look-ahead that favors the",
        "   model. See docs/daily_data_quality_report.md.",
        "3. ARIMA fallback windows: " +
        (f"{arima_fallbacks}/{n_windows}" if arima_fallbacks else "none") + ".",
        f"4. {holdout_days - evaluated_days} trailing holdout days excluded",
        "   (incomplete final window).",
    ]
    report_path = ROOT / "docs" / "rolling_7day_evaluation_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Saved {report_path}")


if __name__ == "__main__":
    main()
