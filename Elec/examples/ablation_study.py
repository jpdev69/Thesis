"""Ablation study: variable contribution of weather and schedule inputs.

Configs (plan section 8, thesis Objective 3 evidence):
1. consumption_only       - weather off, schedule off
2. consumption_weather     - weather on,  schedule off
3. consumption_schedule    - weather off, schedule on
4. full_multivariate       - weather on,  schedule on

All configs share: identical chronological split, epochs, seed, and the same
internal validation block (last 20% of train-block sequences, teacher-forced
one-step-ahead). Calendar encodings intrinsic to the date (day-of-week,
month, holiday flag) remain active in all configs; the ablation isolates
the WEATHER (temperature, humidity, rainfall) and SCHEDULE (has_classes,
is_weekend) inputs, which are neutralized by constants when disabled.

Outputs:
1) data/processed/ablation_results.csv
2) docs/ablation_study_report.md

Expected runtime: 15-25 minutes (4 trainings with early stopping).
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

from src.models.daily_prediction_model import DailyEnergyPredictor

HOLDOUT_RATIO = 0.85
EPOCHS = 100

CONFIGS = [
    ("consumption_only", False, False),
    ("consumption_weather", True, False),
    ("consumption_schedule", False, True),
    ("full_multivariate", True, True),
]


def load_arrays():
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


def ablate(arr, split_idx, weather_on, schedule_on):
    out = dict(arr)
    if not weather_on:
        out["temperature"] = np.full_like(arr["temperature"], arr["temperature"][:split_idx].mean())
        out["humidity"] = np.full_like(arr["humidity"], arr["humidity"][:split_idx].mean())
        out["rainfall"] = np.zeros_like(arr["rainfall"])
    if not schedule_on:
        out["has_classes"] = np.ones_like(arr["has_classes"])
        out["is_weekend"] = np.zeros_like(arr["is_weekend"])
    return out


def main():
    df, arr = load_arrays()
    n = len(df)
    split_idx = int(n * HOLDOUT_RATIO)
    train_dates = df["Date"].iloc[:split_idx].dt.strftime("%Y-%m-%d").tolist()
    print(f"Dataset: {n} days | train block: {split_idx} | "
          f"ablation evaluated on internal validation (last 20% of train block)")

    results = []
    for name, weather_on, schedule_on in CONFIGS:
        print(f"\n{'=' * 60}\nConfig: {name} "
              f"(weather={'ON' if weather_on else 'OFF'}, "
              f"schedule={'ON' if schedule_on else 'OFF'})\n{'=' * 60}")
        a = ablate(arr, split_idx, weather_on, schedule_on)
        model = DailyEnergyPredictor(sequence_length=7)
        model.train(
            consumption=a["consumption"][:split_idx],
            temperature=a["temperature"][:split_idx],
            humidity=a["humidity"][:split_idx],
            rainfall=a["rainfall"][:split_idx],
            has_classes=a["has_classes"][:split_idx],
            day_of_week=a["day_of_week"][:split_idx],
            is_weekend=a["is_weekend"][:split_idx],
            dates=train_dates,
            epochs=EPOCHS,
            validation_split=0.2,
        )
        vm = model.validation_metrics
        results.append({
            "config": name,
            "weather": int(weather_on),
            "schedule": int(schedule_on),
            "RMSE": vm["RMSE"],
            "MAE": vm["MAE"],
            "MAPE": vm["MAPE"],
            "R2": vm["R2"],
            "directional_accuracy": vm["directional_accuracy"],
        })

    res_df = pd.DataFrame(results)
    base = res_df[res_df["config"] == "consumption_only"].iloc[0]
    res_df["MAPE_improvement_vs_base_pp"] = base["MAPE"] - res_df["MAPE"]
    res_df["R2_improvement_vs_base"] = res_df["R2"] - base["R2"]

    out_path = ROOT / "data" / "processed" / "ablation_results.csv"
    res_df.to_csv(out_path, index=False)
    print(f"\nSaved {out_path}")

    print("\n=== Ablation Results (internal validation, same split/seed) ===")
    print(res_df.to_string(index=False))

    full = res_df[res_df["config"] == "full_multivariate"].iloc[0]
    weather_only = res_df[res_df["config"] == "consumption_weather"].iloc[0]
    sched_only = res_df[res_df["config"] == "consumption_schedule"].iloc[0]

    rolling_note = ""
    rolling_csv = ROOT / "data" / "processed" / "rolling_7day_metrics.csv"
    if rolling_csv.exists():
        rolling = pd.read_csv(rolling_csv)
        full_row = rolling[rolling["model"] == "Hybrid_LSTM_SVM"]
        if len(full_row):
            r = full_row.iloc[0]
            rolling_note = (
                f"\nFor context, the full multivariate model under the rolling\n"
                f"7-day holdout protocol achieved MAPE {r['MAPE']:.2f}% / "
                f"R2 {r['R2']:.4f}\n(see docs/rolling_7day_evaluation_report.md).\n"
            )

    report = [
        "# Ablation Study Report: Weather and Schedule Variable Contribution",
        "",
        f"Run: seed {SEED}, chronological 85/15 split, {EPOCHS} epochs max",
        "with early stopping, identical configuration across all ablation",
        "arms. Evaluation: internal validation block (last 20% of the train",
        "block, teacher-forced one-step-ahead predictions).",
        "",
        "Disabled variables are neutralized with constants (weather) or",
        "uniform values (schedule) so the corresponding normalized model",
        "features carry zero variance. Calendar encodings intrinsic to the",
        "date (day-of-week, month, holiday flag) remain active in all arms.",
        "",
        "## Results",
        "",
        "| Config | Weather | Schedule | RMSE | MAE | MAPE | R2 | DirAcc |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in res_df.iterrows():
        report.append(
            f"| {r['config']} | {'on' if r['weather'] else 'off'} | "
            f"{'on' if r['schedule'] else 'off'} | {r['RMSE']:.1f} | "
            f"{r['MAE']:.1f} | {r['MAPE']:.2f}% | {r['R2']:.4f} | "
            f"{r['directional_accuracy']:.1f}% |"
        )
    report += [
        "",
        "## Variable Contribution (vs consumption-only baseline)",
        "",
        f"- Weather alone: MAPE {base['MAPE']:.2f}% -> "
        f"{weather_only['MAPE']:.2f}% "
        f"({base['MAPE'] - weather_only['MAPE']:+.2f} pp), "
        f"R2 {base['R2']:.4f} -> {weather_only['R2']:.4f}",
        f"- Schedule alone: MAPE {base['MAPE']:.2f}% -> "
        f"{sched_only['MAPE']:.2f}% "
        f"({base['MAPE'] - sched_only['MAPE']:+.2f} pp), "
        f"R2 {base['R2']:.4f} -> {sched_only['R2']:.4f}",
        f"- Full multivariate: MAPE {base['MAPE']:.2f}% -> "
        f"{full['MAPE']:.2f}% "
        f"({base['MAPE'] - full['MAPE']:+.2f} pp), "
        f"R2 {base['R2']:.4f} -> {full['R2']:.4f}",
        "",
        rolling_note,
        "## Interpretation Guide",
        "",
        "- Positive MAPE improvements and R2 gains for the weather and",
        "  schedule arms quantify the contribution of each exogenous block,",
        "  directly evidencing thesis Objective 3 (weather contribution) and",
        "  Objective 4 (schedule awareness).",
        "- If improvements are small, note that the daily consumption series",
        "  is reconstructed from monthly bills whose within-month shape is",
        "  itself driven by weather and schedule; some exogenous signal is",
        "  therefore already embedded in the target history and cannot be",
        "  fully isolated by input ablation.",
    ]
    report_path = ROOT / "docs" / "ablation_study_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Saved {report_path}")


if __name__ == "__main__":
    main()
