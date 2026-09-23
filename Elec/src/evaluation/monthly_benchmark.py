"""Monthly benchmark runner using processed ISUE-ISELCO deliverables.

Compares:
1) ARIMA baseline
2) Reduced hybrid cascade (MLP feature extractor -> SVR regressor)

Targets:
- next-month total_kwh
- next-month total_gross_capped
"""

from __future__ import annotations

import argparse
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline


FEATURE_COLUMNS = [
    "coverage_ratio",
    "active_meter_count",
    "kwh_lag_1",
    "kwh_lag_2",
    "kwh_lag_3",
    "kwh_lag_6",
    "kwh_lag_12",
    "gross_lag_1",
    "gross_lag_2",
    "gross_lag_3",
    "gross_lag_6",
    "gross_lag_12",
    "unit_cost_lag_1",
    "unit_cost_lag_3",
    "unit_cost_lag_6",
    "unit_cost_lag_12",
    "kwh_mom_pct",
    "gross_mom_pct",
    "unit_cost_mom_pct",
    "kwh_roll_mean_3",
    "kwh_roll_mean_6",
    "kwh_roll_std_3",
    "kwh_roll_std_6",
    "gross_roll_mean_3",
    "gross_roll_mean_6",
    "unit_cost_roll_mean_3",
    "month_sin",
    "month_cos",
]


@dataclass
class SplitResult:
    train_df: pd.DataFrame
    test_df: pd.DataFrame
    test_start: pd.Timestamp
    test_end: pd.Timestamp


class ReducedHybridCascade:
    """Reduced hybrid for monthly data-limited setting.

    Stage 1: MLP regressor extracts non-linear latent forecast signal.
    Stage 2: SVR learns final mapping from [X, latent, latent^2] -> target.
    """

    def __init__(self, random_state: int = 42):
        self.x_scaler = StandardScaler()
        self.y_scaler = StandardScaler()
        self.feature_extractor = MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            alpha=1e-3,
            learning_rate_init=1e-3,
            max_iter=3000,
            random_state=random_state,
        )
        self.svm = SVR(kernel="rbf", C=50.0, epsilon=0.05, gamma="scale")
        self.is_trained = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64).reshape(-1, 1)

        Xs = self.x_scaler.fit_transform(X)
        ys = self.y_scaler.fit_transform(y).ravel()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.feature_extractor.fit(Xs, ys)

        latent = self.feature_extractor.predict(Xs).reshape(-1, 1)
        X_hybrid = np.column_stack([Xs, latent, latent ** 2])
        self.svm.fit(X_hybrid, ys)
        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Model not trained")

        X = np.asarray(X, dtype=np.float64)
        Xs = self.x_scaler.transform(X)
        latent = self.feature_extractor.predict(Xs).reshape(-1, 1)
        X_hybrid = np.column_stack([Xs, latent, latent ** 2])
        y_scaled = self.svm.predict(X_hybrid).reshape(-1, 1)
        y = self.y_scaler.inverse_transform(y_scaled).ravel()
        return y


def _validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {name}: {missing}")


def _build_supervised_frame(feature_df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    df = feature_df.copy()
    df["period"] = pd.to_datetime(df["period"])
    df["forecast_period"] = df["period"] + pd.offsets.MonthBegin(1)
    df = df[df["is_trainable_row"] == True].copy()  # noqa: E712
    df = df[df[target_col].notna()].copy()
    df = df.dropna(subset=FEATURE_COLUMNS)
    df = df.sort_values("forecast_period").reset_index(drop=True)
    return df


def _chrono_split(df: pd.DataFrame, test_horizon: int) -> SplitResult:
    if len(df) <= test_horizon + 8:
        raise ValueError(
            f"Not enough supervised rows ({len(df)}) for test_horizon={test_horizon}."
        )
    split_idx = len(df) - test_horizon
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    return SplitResult(
        train_df=train_df,
        test_df=test_df,
        test_start=pd.Timestamp(test_df["forecast_period"].iloc[0]),
        test_end=pd.Timestamp(test_df["forecast_period"].iloc[-1]),
    )


def _core_metrics(metrics: dict) -> dict:
    return {
        "RMSE": float(metrics["RMSE"]),
        "MAE": float(metrics["MAE"]),
        "MAPE": float(metrics["MAPE"]),
        "R2": float(metrics["R2"]),
    }


def _run_target_benchmark(
    feature_df: pd.DataFrame,
    campus_df: pd.DataFrame,
    target_name: str,
    hybrid_target_col: str,
    arima_series_col: str,
    test_horizon: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    supervised = _build_supervised_frame(feature_df, hybrid_target_col)
    split = _chrono_split(supervised, test_horizon=test_horizon)

    X_train = split.train_df[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    y_train = split.train_df[hybrid_target_col].to_numpy(dtype=np.float64)
    X_test = split.test_df[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    y_test = split.test_df[hybrid_target_col].to_numpy(dtype=np.float64)

    hybrid = ReducedHybridCascade(random_state=42)
    hybrid.fit(X_train, y_train)
    hybrid_pred = hybrid.predict(X_test)

    hybrid_metrics = _core_metrics(
        ForecastingMetrics.calculate_all_metrics(y_test, hybrid_pred)
    )

    campus = campus_df.copy()
    campus["period"] = pd.to_datetime(campus["period"])
    campus = campus[campus[arima_series_col].notna()].sort_values("period")

    test_periods = list(split.test_df["forecast_period"])
    test_start = split.test_df["forecast_period"].iloc[0]

    train_series = campus[campus["period"] < test_start][arima_series_col].to_numpy(dtype=np.float64)
    test_series_df = campus[campus["period"].isin(test_periods)].sort_values("period")
    test_series = test_series_df[arima_series_col].to_numpy(dtype=np.float64)

    if len(test_series) != len(y_test):
        raise ValueError(
            f"ARIMA test series length mismatch for {target_name}: "
            f"arima={len(test_series)} vs hybrid={len(y_test)}"
        )

    arima = ARIMABaseline()
    arima_eval = arima.evaluate(train_series, test_series)
    arima_pred = np.array(arima_eval["predictions"], dtype=np.float64)
    arima_metrics = _core_metrics(arima_eval["metrics"])

    metrics_rows = [
        {
            "target_variable": target_name,
            "model": "Reduced_Hybrid_Cascade",
            "train_points": int(len(y_train)),
            "test_points": int(len(y_test)),
            "test_start": split.test_start.strftime("%Y-%m"),
            "test_end": split.test_end.strftime("%Y-%m"),
            **hybrid_metrics,
        },
        {
            "target_variable": target_name,
            "model": "ARIMA_Baseline",
            "train_points": int(len(train_series)),
            "test_points": int(len(test_series)),
            "test_start": split.test_start.strftime("%Y-%m"),
            "test_end": split.test_end.strftime("%Y-%m"),
            "arima_order": arima_eval.get("order"),
            "arima_used_fallback": bool(arima_eval.get("used_fallback", False)),
            "arima_fallback_reason": arima_eval.get("fallback_reason"),
            **arima_metrics,
        },
    ]

    pred_rows = []
    for i, period in enumerate(test_periods):
        actual = float(y_test[i])
        pred_h = float(hybrid_pred[i])
        pred_a = float(arima_pred[i])
        err_h = abs(actual - pred_h)
        err_a = abs(actual - pred_a)
        pred_rows.append(
            {
                "target_variable": target_name,
                "forecast_period": pd.Timestamp(period).strftime("%Y-%m"),
                "actual": actual,
                "pred_reduced_hybrid": pred_h,
                "pred_arima": pred_a,
                "abs_error_reduced_hybrid": err_h,
                "abs_error_arima": err_a,
                "better_model": "Reduced_Hybrid_Cascade" if err_h <= err_a else "ARIMA_Baseline",
            }
        )

    return pd.DataFrame(metrics_rows), pd.DataFrame(pred_rows)


def _markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(str(val))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep, *rows])


def _write_report(
    report_path: Path,
    metrics_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    feature_path: Path,
    campus_path: Path,
) -> None:
    metrics_view = metrics_df[
        [
            "target_variable",
            "model",
            "train_points",
            "test_points",
            "test_start",
            "test_end",
            "RMSE",
            "MAE",
            "MAPE",
            "R2",
        ]
    ].copy()

    winner_rows = []
    for target in sorted(metrics_df["target_variable"].unique()):
        sub = metrics_df[metrics_df["target_variable"] == target]
        hybrid = sub[sub["model"] == "Reduced_Hybrid_Cascade"].iloc[0]
        arima = sub[sub["model"] == "ARIMA_Baseline"].iloc[0]

        def reduction(b, i):
            return 0.0 if b == 0 else ((b - i) / b) * 100.0

        winner_rows.append(
            {
                "target_variable": target,
                "RMSE_reduction_hybrid_vs_arima_pct": reduction(arima["RMSE"], hybrid["RMSE"]),
                "MAE_reduction_hybrid_vs_arima_pct": reduction(arima["MAE"], hybrid["MAE"]),
                "MAPE_reduction_hybrid_vs_arima_pct": reduction(arima["MAPE"], hybrid["MAPE"]),
                "R2_gain_hybrid_minus_arima": hybrid["R2"] - arima["R2"],
            }
        )
    winners_df = pd.DataFrame(winner_rows)

    best_count = (
        preds_df.groupby(["target_variable", "better_model"]).size().rename("count").reset_index()
    )

    text = "\n".join(
        [
            "# Monthly Benchmark Report (Chapter 4 Ready)",
            "",
            "## Scope",
            "",
            "- Baseline: ARIMA on chronological monthly series.",
            "- Comparator: Reduced Hybrid Cascade (MLP feature extractor -> SVR regressor).",
            "- Targets: next-month campus `kWh` and next-month campus `Gross (capped)`.",
            "- Data inputs:",
            f"  - `{feature_path}`",
            f"  - `{campus_path}`",
            "",
            "## Why this setup is defendable",
            "",
            "- ARIMA is the classical time-series baseline required for objective comparison.",
            "- Reduced hybrid uses only information available from your cleaned monthly data and avoids external leakage.",
            "- Chronological holdout preserves real forecasting order.",
            "- Same test horizon is used for both models per target.",
            "",
            "## Core Metrics",
            "",
            _markdown_table(metrics_view),
            "",
            "## Hybrid vs ARIMA Improvement",
            "",
            _markdown_table(winners_df),
            "",
            "## Per-Month Winner Count",
            "",
            _markdown_table(best_count),
            "",
            "## Interpretation Notes",
            "",
            "- If hybrid improves RMSE/MAE/MAPE and raises R2, it supports the value of feature-enriched non-linear modeling under limited variables.",
            "- If ARIMA remains competitive, it indicates strong autoregressive signal in monthly billing and should be reported as a robust baseline.",
            "- Both outcomes are publishable as long as methodology is transparent and split discipline is preserved.",
        ]
    )
    report_path.write_text(text, encoding="utf-8")


def run(
    feature_path: Path,
    campus_path: Path,
    out_metrics: Path,
    out_predictions: Path,
    report_path: Path,
    test_horizon: int,
) -> None:
    feature_df = pd.read_csv(feature_path)
    campus_df = pd.read_csv(campus_path)

    _validate_columns(feature_df, ["period", "is_trainable_row", *FEATURE_COLUMNS], "feature_table")
    _validate_columns(
        feature_df,
        ["target_kwh_next_month", "target_gross_next_month"],
        "feature_table",
    )
    _validate_columns(campus_df, ["period", "total_kwh_clean", "total_gross_capped"], "campus_aggregate")

    metrics_all = []
    preds_all = []

    target_specs = [
        ("kwh_next_month", "target_kwh_next_month", "total_kwh_clean"),
        ("gross_next_month", "target_gross_next_month", "total_gross_capped"),
    ]

    for target_name, hybrid_target_col, arima_series_col in target_specs:
        metrics_df, preds_df = _run_target_benchmark(
            feature_df=feature_df,
            campus_df=campus_df,
            target_name=target_name,
            hybrid_target_col=hybrid_target_col,
            arima_series_col=arima_series_col,
            test_horizon=test_horizon,
        )
        metrics_all.append(metrics_df)
        preds_all.append(preds_df)

    metrics_out = pd.concat(metrics_all, ignore_index=True)
    preds_out = pd.concat(preds_all, ignore_index=True)

    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_out.to_csv(out_metrics, index=False)
    preds_out.to_csv(out_predictions, index=False)
    _write_report(report_path, metrics_out, preds_out, feature_path, campus_path)

    print("Monthly benchmark completed.")
    print(f"- {out_metrics}")
    print(f"- {out_predictions}")
    print(f"- {report_path}")


def main() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    default_feature = base_dir / "data" / "processed" / "feature_table_monthly.csv"
    default_campus = base_dir / "data" / "processed" / "campus_month_aggregate.csv"
    default_out_metrics = base_dir / "data" / "processed" / "monthly_benchmark_metrics.csv"
    default_out_preds = base_dir / "data" / "processed" / "monthly_benchmark_predictions.csv"
    default_report = base_dir / "docs" / "monthly_benchmark_report.md"

    parser = argparse.ArgumentParser(description="Run monthly benchmark on processed ISELCO data")
    parser.add_argument("--feature-path", type=Path, default=default_feature)
    parser.add_argument("--campus-path", type=Path, default=default_campus)
    parser.add_argument("--out-metrics", type=Path, default=default_out_metrics)
    parser.add_argument("--out-predictions", type=Path, default=default_out_preds)
    parser.add_argument("--report-path", type=Path, default=default_report)
    parser.add_argument("--test-horizon", type=int, default=6)
    args = parser.parse_args()

    run(
        feature_path=args.feature_path,
        campus_path=args.campus_path,
        out_metrics=args.out_metrics,
        out_predictions=args.out_predictions,
        report_path=args.report_path,
        test_horizon=args.test_horizon,
    )


if __name__ == "__main__":
    main()
