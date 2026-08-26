"""
Daily Energy Prediction API
Supports weather-aware and schedule-aware predictions
plus ARIMA baseline benchmarking for thesis objective completion.
"""

from datetime import datetime
import os
import sys

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline
from src.models.daily_prediction_model import DailyEnergyPredictor, HAS_TF

app = FastAPI(title="Daily Campus Energy Forecasting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model state
model_state = {
    "model": None,
    "is_trained": False,
    "last_trained": None,
    "baseline_comparison": None,
    "validation_metrics": None,
    "training_snapshot": None,
}


class DailyTrainingData(BaseModel):
    consumption: list[float]
    temperature: list[float]
    humidity: list[float]
    rainfall: list[float]
    has_classes: list[int]
    day_of_week: list[int]
    is_weekend: list[int]
    epochs: int = 100


class DailyForecastRequest(BaseModel):
    past_data: dict
    future_weather: dict
    future_schedule: dict
    n_days: int = 7


class ArimaBenchmarkRequest(BaseModel):
    consumption: list[float]
    train_ratio: float = 0.8


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


def _get_split_index(n, train_ratio):
    split_idx = int(n * train_ratio)
    split_idx = max(split_idx, 21)
    split_idx = min(split_idx, n - 7)
    return split_idx


def _arima_univariate_benchmark(consumption, train_ratio=0.8):
    consumption = np.array(consumption, dtype=np.float64)
    n = len(consumption)
    if n < 30:
        raise ValueError("Need at least 30 days of data for ARIMA benchmark")

    split_idx = _get_split_index(n, train_ratio)
    train_series = consumption[:split_idx]
    test_series = consumption[split_idx:]

    if len(test_series) < 7:
        raise ValueError("Need at least 7 test days for ARIMA benchmark")

    arima = ARIMABaseline()
    arima_eval = arima.evaluate(train_series, test_series)

    return {
        "metrics": arima_eval["metrics"],
        "order": arima_eval["order"],
        "used_fallback": arima_eval["used_fallback"],
        "fallback_reason": arima_eval["fallback_reason"],
        "split": {
            "train_days": int(len(train_series)),
            "test_days": int(len(test_series)),
            "train_ratio": float(train_ratio),
            "test_ratio": float(1.0 - train_ratio),
        },
    }


def _hybrid_vs_arima_from_training(consumption, model):
    """Compare trained hybrid model against ARIMA on the same validation horizon."""
    if (
        model.validation_start_index is None
        or model.validation_length is None
        or model.validation_actual is None
        or model.validation_predictions is None
    ):
        return None

    val_start = int(model.validation_start_index)
    val_len = int(model.validation_length)

    train_series = np.array(consumption[:val_start], dtype=np.float64)
    test_series = np.array(consumption[val_start:val_start + val_len], dtype=np.float64)
    hybrid_actual = np.array(model.validation_actual, dtype=np.float64)
    hybrid_preds = np.array(model.validation_predictions, dtype=np.float64)

    horizon = min(len(test_series), len(hybrid_actual), len(hybrid_preds))
    if horizon < 3:
        return None

    test_series = test_series[:horizon]
    hybrid_actual = hybrid_actual[:horizon]
    hybrid_preds = hybrid_preds[:horizon]

    hybrid_full = ForecastingMetrics.calculate_all_metrics(hybrid_actual, hybrid_preds)
    hybrid_metrics = _core_metrics(hybrid_full)

    arima = ARIMABaseline()
    arima_eval = arima.evaluate(train_series, test_series)
    arima_metrics = arima_eval["metrics"]

    improvement = {
        "RMSE_reduction_pct": _reduction_pct(arima_metrics["RMSE"], hybrid_metrics["RMSE"]),
        "MAE_reduction_pct": _reduction_pct(arima_metrics["MAE"], hybrid_metrics["MAE"]),
        "MAPE_reduction_pct": _reduction_pct(arima_metrics["MAPE"], hybrid_metrics["MAPE"]),
        "R2_improvement_pct": _increase_pct(arima_metrics["R2"], hybrid_metrics["R2"]),
    }

    comparison = {
        "Hybrid_LSTM_SVM": hybrid_metrics,
        "ARIMA": arima_metrics,
    }
    best = ForecastingMetrics.compare_models(comparison).get("best_model", {})

    return {
        "metrics": {
            "hybrid": hybrid_metrics,
            "arima": arima_metrics,
        },
        "best_by_metric": best,
        "improvement_hybrid_vs_arima": improvement,
        "arima_details": {
            "order": arima_eval["order"],
            "used_fallback": arima_eval["used_fallback"],
            "fallback_reason": arima_eval["fallback_reason"],
        },
        "validation_split": {
            "train_days": int(len(train_series)),
            "validation_days": int(horizon),
            "validation_start_index": val_start,
        },
    }


@app.get("/")
async def root():
    return {
        "message": "Daily Campus Energy Forecasting API",
        "version": "2.1.0",
        "features": [
            "weather-aware",
            "schedule-aware",
            "daily-predictions",
            "arima-baseline-benchmark",
        ],
        "model": "Enhanced LSTM-SVM Hybrid + ARIMA Baseline",
    }


@app.post("/train-daily")
async def train_daily_model(data: DailyTrainingData):
    """Train the daily prediction model with weather and schedule data."""
    try:
        if len(data.consumption) < 30:
            raise HTTPException(
                status_code=400,
                detail="Need at least 30 days of data for training",
            )

        lengths = [
            len(data.consumption),
            len(data.temperature),
            len(data.humidity),
            len(data.rainfall),
            len(data.has_classes),
            len(data.day_of_week),
            len(data.is_weekend),
        ]
        if len(set(lengths)) != 1:
            raise HTTPException(
                status_code=400,
                detail="All data arrays must have the same length",
            )

        consumption = np.array(data.consumption, dtype=np.float64)
        temperature = np.array(data.temperature, dtype=np.float64)
        humidity = np.array(data.humidity, dtype=np.float64)
        rainfall = np.array(data.rainfall, dtype=np.float64)
        has_classes = np.array(data.has_classes, dtype=np.int64)
        day_of_week = np.array(data.day_of_week, dtype=np.int64)
        is_weekend = np.array(data.is_weekend, dtype=np.int64)

        model = DailyEnergyPredictor(sequence_length=7)
        model.train(
            consumption,
            temperature,
            humidity,
            rainfall,
            has_classes,
            day_of_week,
            is_weekend,
            epochs=data.epochs,
            validation_split=0.2,
        )

        baseline_comparison = _hybrid_vs_arima_from_training(consumption, model)

        model_state["model"] = model
        model_state["is_trained"] = True
        model_state["last_trained"] = datetime.now().isoformat()
        model_state["baseline_comparison"] = baseline_comparison
        model_state["validation_metrics"] = model.validation_metrics
        model_state["training_snapshot"] = {
            "consumption": consumption.tolist(),
            "temperature": temperature.tolist(),
            "humidity": humidity.tolist(),
            "rainfall": rainfall.tolist(),
            "has_classes": has_classes.tolist(),
            "day_of_week": day_of_week.tolist(),
            "is_weekend": is_weekend.tolist(),
        }

        return {
            "status": "success",
            "message": "Daily prediction model trained successfully",
            "data_points": int(len(consumption)),
            "training_days": int(len(consumption)),
            "last_trained": model_state["last_trained"],
            "validation_metrics": model.validation_metrics,
            "baseline_comparison": baseline_comparison,
            "runtime": {
                "uses_tensorflow_lstm": bool(HAS_TF),
                "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/forecast-daily")
async def forecast_daily(request: DailyForecastRequest):
    """Generate daily forecasts for next N days."""
    try:
        if not model_state["is_trained"]:
            raise HTTPException(
                status_code=400,
                detail="Model not trained. Please train the model first.",
            )

        model = model_state["model"]

        past_data = {k: np.array(v) for k, v in request.past_data.items()}
        future_weather = {k: np.array(v) for k, v in request.future_weather.items()}
        future_schedule = {k: np.array(v) for k, v in request.future_schedule.items()}

        forecast_result = model.predict_next_n_days(
            past_data,
            future_weather,
            future_schedule,
            n_days=request.n_days,
        )

        predictions = np.array(forecast_result["predictions"], dtype=np.float64)
        lower = np.array(forecast_result["lower"], dtype=np.float64)
        upper = np.array(forecast_result["upper"], dtype=np.float64)

        cost_per_kwh = 12.383
        costs = predictions * cost_per_kwh

        return {
            "status": "success",
            "predictions": predictions.tolist(),
            "lower": lower.tolist(),
            "upper": upper.tolist(),
            "anomaly_flags": list(forecast_result.get("anomaly_flags", [])),
            "peak_analysis": forecast_result.get("peak_analysis", {}),
            "costs": costs.tolist(),
            "n_days": int(request.n_days),
            "total_consumption": float(predictions.sum()),
            "total_cost": float(costs.sum()),
            "avg_daily_consumption": float(predictions.mean()),
            "avg_daily_cost": float(costs.mean()),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/benchmark-arima")
async def benchmark_arima(request: ArimaBenchmarkRequest):
    """Compute ARIMA baseline metrics on a chronological holdout split."""
    try:
        if len(request.consumption) < 30:
            raise HTTPException(
                status_code=400,
                detail="Need at least 30 days of consumption data",
            )
        if request.train_ratio <= 0.5 or request.train_ratio >= 0.95:
            raise HTTPException(
                status_code=400,
                detail="train_ratio must be between 0.5 and 0.95",
            )

        benchmark = _arima_univariate_benchmark(
            request.consumption,
            train_ratio=request.train_ratio,
        )
        return {
            "status": "success",
            "benchmark": benchmark,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/baseline-comparison")
async def baseline_comparison():
    """Return latest hybrid-vs-ARIMA comparison from training run."""
    if not model_state["is_trained"]:
        raise HTTPException(
            status_code=400,
            detail="Model not trained. Run /train-daily first.",
        )
    return {
        "status": "success",
        "baseline_comparison": model_state.get("baseline_comparison"),
        "last_trained": model_state.get("last_trained"),
    }


@app.get("/model-status")
async def model_status():
    """Get current model status."""
    training_snapshot = model_state.get("training_snapshot") or {}
    return {
        "is_trained": model_state["is_trained"],
        "last_trained": model_state["last_trained"],
        "model_type": "Enhanced LSTM-SVM Hybrid",
        "features": [
            "consumption",
            "temperature",
            "humidity",
            "rainfall",
            "has_classes",
            "day_of_week",
            "is_weekend",
        ],
        "has_baseline_comparison": model_state.get("baseline_comparison") is not None,
        "training_days": int(len(training_snapshot.get("consumption", []))),
        "runtime": {
            "uses_tensorflow_lstm": bool(HAS_TF),
            "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
        },
    }


@app.get("/metrics")
async def metrics_snapshot():
    """Compatibility endpoint for analytics view.

    Returns latest validation metrics when available.
    """
    if not model_state["is_trained"]:
        return {
            "status": "not_trained",
            "is_trained": False,
            "validation_metrics": None,
            "baseline_comparison": None,
            "training_snapshot": None,
            "last_trained": model_state.get("last_trained"),
            "runtime": {
                "uses_tensorflow_lstm": bool(HAS_TF),
                "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
            },
        }

    return {
        "status": "success",
        "is_trained": True,
        "validation_metrics": model_state.get("validation_metrics"),
        "baseline_comparison": model_state.get("baseline_comparison"),
        "training_snapshot": model_state.get("training_snapshot"),
        "last_trained": model_state.get("last_trained"),
        "runtime": {
            "uses_tensorflow_lstm": bool(HAS_TF),
            "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
        },
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_trained": model_state["is_trained"],
        "api_version": "2.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("Daily Campus Energy Forecasting API")
    print("Weather-Aware & Schedule-Aware Predictions")
    print("ARIMA Baseline Benchmark Enabled")
    print("=" * 70)
    print("\nStarting server on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nFeatures:")
    print("  [x] Daily consumption predictions")
    print("  [x] Weather integration (temperature, humidity, rainfall)")
    print("  [x] Class schedule awareness")
    print("  [x] Enhanced LSTM-SVM hybrid model")
    print("  [x] ARIMA baseline benchmark")
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=8000)
