"""Thesis benchmark utilities for Hybrid LSTM-SVM vs ARIMA comparison."""

import numpy as np

from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline
from src.models.daily_prediction_model import DailyEnergyPredictor


def _core_metrics(metrics):
    return {
        "RMSE": float(metrics["RMSE"]),
        "MAE": float(metrics["MAE"]),
        "MAPE": float(metrics["MAPE"]),
        "R2": float(metrics["R2"]),
    }


def _reduction_pct(baseline, improved):
    if baseline == 0:
        return 0.0
    return float(((baseline - improved) / baseline) * 100.0)


def _increase_pct(baseline, improved):
    denom = abs(baseline) if baseline != 0 else 1.0
    return float(((improved - baseline) / denom) * 100.0)


def run_hybrid_vs_arima_benchmark(
    consumption,
    temperature,
    humidity,
    rainfall,
    has_classes,
    day_of_week,
    is_weekend,
    dates=None,
    sequence_length=7,
    train_ratio=0.8,
    epochs=100,
):
    """Run out-of-sample benchmark for hybrid model against ARIMA.

    Uses a chronological split:
      - train: first train_ratio chunk
      - test: remaining chunk

    Hybrid prediction mode on test chunk:
      - recursive multi-step forecast with known exogenous test arrays

    ARIMA prediction mode on test chunk:
      - univariate multi-step forecast from train consumption history
    """
    consumption = np.array(consumption, dtype=np.float64)
    temperature = np.array(temperature, dtype=np.float64)
    humidity = np.array(humidity, dtype=np.float64)
    rainfall = np.array(rainfall, dtype=np.float64)
    has_classes = np.array(has_classes, dtype=np.int64)
    day_of_week = np.array(day_of_week, dtype=np.int64)
    is_weekend = np.array(is_weekend, dtype=np.int64)

    n = len(consumption)
    if n < 40:
        raise ValueError("Need at least 40 days to run reliable ARIMA benchmark.")

    split_idx = int(n * train_ratio)
    split_idx = max(split_idx, sequence_length + 14)
    split_idx = min(split_idx, n - 7)

    if split_idx <= sequence_length or split_idx >= n:
        raise ValueError("Unable to create valid train/test split for benchmark.")

    train_slice = slice(0, split_idx)
    test_slice = slice(split_idx, n)

    train_consumption = consumption[train_slice]
    test_consumption = consumption[test_slice]

    if len(test_consumption) < 7:
        raise ValueError("Benchmark test horizon is too short. Provide more data.")

    train_dates = None
    if dates is not None:
        train_dates = list(dates[:split_idx])

    hybrid_model = DailyEnergyPredictor(sequence_length=sequence_length)
    hybrid_model.train(
        consumption=train_consumption,
        temperature=temperature[train_slice],
        humidity=humidity[train_slice],
        rainfall=rainfall[train_slice],
        has_classes=has_classes[train_slice],
        day_of_week=day_of_week[train_slice],
        is_weekend=is_weekend[train_slice],
        dates=train_dates,
        epochs=epochs,
        validation_split=0.2,
    )

    past_data = {
        "consumption": consumption[max(0, split_idx - sequence_length):split_idx],
        "temperature": temperature[max(0, split_idx - sequence_length):split_idx],
        "humidity": humidity[max(0, split_idx - sequence_length):split_idx],
        "rainfall": rainfall[max(0, split_idx - sequence_length):split_idx],
        "has_classes": has_classes[max(0, split_idx - sequence_length):split_idx],
        "day_of_week": day_of_week[max(0, split_idx - sequence_length):split_idx],
        "is_weekend": is_weekend[max(0, split_idx - sequence_length):split_idx],
    }

    future_weather = {
        "temperature": temperature[test_slice],
        "humidity": humidity[test_slice],
        "rainfall": rainfall[test_slice],
    }
    future_schedule = {
        "has_classes": has_classes[test_slice],
        "day_of_week": day_of_week[test_slice],
        "is_weekend": is_weekend[test_slice],
    }

    hybrid_result = hybrid_model.predict_next_n_days(
        past_data,
        future_weather,
        future_schedule,
        n_days=len(test_consumption),
    )
    hybrid_preds = np.array(hybrid_result["predictions"], dtype=np.float64)
    hybrid_full_metrics = ForecastingMetrics.calculate_all_metrics(test_consumption, hybrid_preds)
    hybrid_metrics = _core_metrics(hybrid_full_metrics)

    arima_model = ARIMABaseline()
    arima_eval = arima_model.evaluate(train_consumption, test_consumption)
    arima_preds = np.array(arima_eval["predictions"], dtype=np.float64)
    arima_metrics = arima_eval["metrics"]

    comparison = {
        "Hybrid_LSTM_SVM": hybrid_metrics,
        "ARIMA": arima_metrics,
    }
    best_by_metric = ForecastingMetrics.compare_models(comparison)["best_model"]

    improvement = {
        "RMSE_reduction_pct": _reduction_pct(arima_metrics["RMSE"], hybrid_metrics["RMSE"]),
        "MAE_reduction_pct": _reduction_pct(arima_metrics["MAE"], hybrid_metrics["MAE"]),
        "MAPE_reduction_pct": _reduction_pct(arima_metrics["MAPE"], hybrid_metrics["MAPE"]),
        "R2_improvement_pct": _increase_pct(arima_metrics["R2"], hybrid_metrics["R2"]),
    }

    return {
        "split": {
            "train_days": int(len(train_consumption)),
            "test_days": int(len(test_consumption)),
            "train_ratio": float(train_ratio),
            "test_ratio": float(1.0 - train_ratio),
            "sequence_length": int(sequence_length),
        },
        "metrics": comparison,
        "best_by_metric": best_by_metric,
        "improvement_hybrid_vs_arima": improvement,
        "arima_details": {
            "order": arima_eval["order"],
            "used_fallback": bool(arima_eval["used_fallback"]),
            "fallback_reason": arima_eval["fallback_reason"],
        },
        "predictions": {
            "actual": test_consumption.tolist(),
            "hybrid": hybrid_preds.tolist(),
            "arima": arima_preds.tolist(),
        },
    }
