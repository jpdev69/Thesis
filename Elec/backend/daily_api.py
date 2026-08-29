"""
Daily Energy Prediction API
Supports weather-aware and schedule-aware predictions
plus ARIMA baseline benchmarking for thesis objective completion.

Also serves the operational model trained by examples/daily_update.py:
on startup it auto-loads models/ops/daily/ so /forecast-daily,
/model-status, /metrics and the comparison matrix endpoints reflect
the continuously-retrained hybrid LSTM-SVM, and /ops/forecast exposes
the latest daily 7-day forecast artifact.
"""

from datetime import datetime, timedelta
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.build_daily_canonical import has_classes_on
from src.data.weather_client import fetch_forecast_blend
from src.evaluation.metrics import ForecastingMetrics
from src.models.arima_baseline import ARIMABaseline
from src.models.daily_prediction_model import DailyEnergyPredictor, HAS_TF

ELEC_ROOT = Path(__file__).resolve().parents[1]
OPS_MODEL_DIR = ELEC_ROOT / "models" / "ops" / "daily"
OPS_STATE_PATH = ELEC_ROOT / "models" / "ops" / "state.json"
OPS_CSV = ELEC_ROOT / "data" / "daily_ops_dataset.csv"
LATEST_FORECAST_PATH = ELEC_ROOT / "data" / "processed" / "ops" / "latest_forecast.json"
COST_PER_KWH = 12.383

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
    # "ops_disk" when auto-loaded from models/ops/daily/,
    # "in_memory" when trained via POST /train-daily
    "source": None,
    "ops_state": None,
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


def _read_json(path) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _ops_model_available() -> bool:
    return (OPS_MODEL_DIR / "daily_meta.joblib").exists()


def _try_load_ops_model() -> None:
    """Load the operational model trained by examples/daily_update.py."""
    if not _ops_model_available():
        return
    try:
        model = DailyEnergyPredictor(sequence_length=7)
        model.load(OPS_MODEL_DIR)
        ops_state = _read_json(OPS_STATE_PATH) or {}
        model_state["model"] = model
        model_state["is_trained"] = True
        model_state["source"] = "ops_disk"
        model_state["last_trained"] = ops_state.get("last_trained_at")
        model_state["validation_metrics"] = ops_state.get("last_train_metrics")
        model_state["ops_state"] = ops_state
        print(
            "Operational model loaded from models/ops/daily/ "
            f"(trained {ops_state.get('last_trained_at', 'n/a')})"
        )
    except Exception as e:
        print(f"[!] Could not load operational model: {e}")


def _load_ops_series() -> pd.DataFrame | None:
    try:
        df = pd.read_csv(OPS_CSV, parse_dates=["Date"]).sort_values("Date")
        return df
    except Exception:
        return None


def _ops_training_snapshot() -> dict | None:
    """Training snapshot built from the anchored (bill-backed) ops rows.

    Used by /metrics so the frontend hydration and the models.html
    comparison matrix receive real historical data even when the model
    was trained by the daily script rather than via POST /train-daily.
    """
    df = _load_ops_series()
    if df is None:
        return None
    anchored = df[df["IsDisaggregated"] == 1]
    if len(anchored) < 30:
        return None
    return {
        "consumption": [round(float(v), 4) for v in anchored["Consumption"]],
        "temperature": [round(float(v), 4) for v in anchored["Temperature"]],
        "humidity": [round(float(v), 4) for v in anchored["Humidity"]],
        "rainfall": [round(float(v), 4) for v in anchored["Rainfall"]],
        "has_classes": [int(v) for v in anchored["HasClasses"]],
        "day_of_week": [int(v) for v in anchored["DayOfWeek"]],
        "is_weekend": [int(v) for v in anchored["IsWeekend"]],
        "dates": anchored["Date"].dt.strftime("%Y-%m-%d").tolist(),
    }


def _ops_summary() -> dict:
    ops_state = model_state.get("ops_state") or _read_json(OPS_STATE_PATH) or {}
    df = _load_ops_series()
    anchored_days = provisional_days = data_through = None
    if df is not None:
        anchored_days = int((df["IsDisaggregated"] == 1).sum())
        provisional_days = int((df["IsDisaggregated"] == 0).sum())
        data_through = str(df["Date"].max().date())
    return {
        "available": _ops_model_available(),
        "model_trained_at": ops_state.get("last_trained_at"),
        "last_run": ops_state.get("last_run"),
        "last_forecast_at": ops_state.get("last_forecast_at"),
        "validation_metrics": ops_state.get("last_train_metrics"),
        "anchored_months": len(ops_state.get("anchored_months") or []),
        "anchored_days": anchored_days,
        "provisional_days": provisional_days,
        "data_through": data_through,
        "forecast_available": LATEST_FORECAST_PATH.exists(),
    }


def _ops_forecast_payload(n_days: int) -> dict:
    """Recompute the operational forecast live (model + ops series + live weather)."""
    if not model_state.get("is_trained") or model_state.get("source") != "ops_disk":
        _try_load_ops_model()
    if not model_state.get("is_trained") or model_state.get("source") != "ops_disk":
        raise HTTPException(
            status_code=400,
            detail="Operational model not available. Run examples/daily_update.py first.",
        )

    df = _load_ops_series()
    if df is None or len(df) < 30:
        raise HTTPException(status_code=400, detail="Operational dataset not available.")

    model = model_state["model"]
    past_rows = df.tail(30)
    past = {
        "consumption": past_rows["Consumption"].to_numpy(float),
        "temperature": past_rows["Temperature"].to_numpy(float),
        "humidity": past_rows["Humidity"].to_numpy(float),
        "rainfall": past_rows["Rainfall"].to_numpy(float),
        "has_classes": past_rows["HasClasses"].to_numpy(int),
        "day_of_week": past_rows["DayOfWeek"].to_numpy(int),
        "is_weekend": past_rows["IsWeekend"].to_numpy(int),
    }

    fc_start = df["Date"].max() + pd.Timedelta(days=1)
    fc_dates = [fc_start + pd.Timedelta(days=i) for i in range(n_days)]

    weather_source = "open_meteo_forecast"
    blend = {}
    try:
        # Open-Meteo serves at most 16 forecast days; longer horizons
        # are filled with persistence values per-day below.
        blend = fetch_forecast_blend(past_days=7, forecast_days=min(max(n_days, 7) + 1, 16))
    except Exception as e:
        print(f"[!] Weather forecast fetch failed ({e}); using persistence")
        weather_source = "persistence_fallback"

    recent = df.tail(7)
    t_mean = float(recent["Temperature"].mean())
    h_mean = float(recent["Humidity"].mean())
    r_mean = float(recent["Rainfall"].mean())
    temps, hums, rains = [], [], []
    for d in fc_dates:
        vals = blend.get(d.strftime("%Y-%m-%d"))
        if vals is not None and all(v is not None for v in vals):
            temps.append(float(vals[0]))
            hums.append(float(vals[1]))
            rains.append(float(vals[2]))
        else:
            temps.append(t_mean)
            hums.append(h_mean)
            rains.append(r_mean)

    future_schedule = {
        "has_classes": np.array([has_classes_on(d.date()) for d in fc_dates]),
        "day_of_week": np.array([d.weekday() for d in fc_dates]),
        "is_weekend": np.array([int(d.weekday() >= 5) for d in fc_dates]),
    }
    future_weather = {
        "temperature": np.array(temps),
        "humidity": np.array(hums),
        "rainfall": np.array(rains),
    }

    result = model.predict_next_n_days(past, future_weather, future_schedule, n_days=n_days)
    preds = np.asarray(result["predictions"], dtype=float)
    lower = np.asarray(result["lower"], dtype=float)
    upper = np.asarray(result["upper"], dtype=float)
    costs = preds * COST_PER_KWH

    peak = result.get("peak_analysis", {})
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "forecast_start": str(fc_dates[0].date()),
        "forecast_days": int(n_days),
        "weather_source": weather_source,
        "cost_per_kwh": COST_PER_KWH,
        "data_through": str(df["Date"].max().date()),
        "anchored_days": int((df["IsDisaggregated"] == 1).sum()),
        "provisional_days": int((df["IsDisaggregated"] == 0).sum()),
        "dates": [str(d.date()) for d in fc_dates],
        "predictions_kwh": [float(v) for v in preds],
        "lower95_kwh": [float(v) for v in lower],
        "upper95_kwh": [float(v) for v in upper],
        "cost_php": [float(v) for v in costs],
        "has_classes": [int(v) for v in future_schedule["has_classes"]],
        "temperature": [float(v) for v in temps],
        "humidity": [float(v) for v in hums],
        "rainfall": [float(v) for v in rains],
        "anomaly_flags": [bool(f) for f in result.get("anomaly_flags", [])],
        "peak_analysis": {
            k: (float(v) if isinstance(v, (int, float)) else v) for k, v in peak.items()
        },
        "total_consumption_kwh": float(preds.sum()),
        "total_cost_php": float(costs.sum()),
    }


def _hybrid_vs_arima_from_ops():
    """Fallback hybrid-vs-ARIMA comparison computed from the ops artifacts.

    Rebuilds the model's one-step validation window on the current
    anchored data (same 80/20 protocol used at training time) and
    evaluates ARIMA on the identical window, so the comparison matrix
    stays available without an in-memory training run.
    """
    if model_state.get("source") != "ops_disk" or not _ops_model_available():
        return None
    try:
        model = model_state["model"]
        df = _load_ops_series()
        if df is None:
            return None
        anchored = df[df["IsDisaggregated"] == 1]
        if len(anchored) < 60:
            return None

        consumption = anchored["Consumption"].to_numpy(float)
        temperature = anchored["Temperature"].to_numpy(float)
        humidity = anchored["Humidity"].to_numpy(float)
        rainfall = anchored["Rainfall"].to_numpy(float)
        has_classes = anchored["HasClasses"].to_numpy(int)
        day_of_week = anchored["DayOfWeek"].to_numpy(int)
        is_weekend = anchored["IsWeekend"].to_numpy(int)
        dates = anchored["Date"].dt.strftime("%Y-%m-%d").tolist()

        features = model.prepare_features(
            consumption, temperature, humidity, rainfall,
            has_classes, day_of_week, is_weekend, dates=dates,
            fit_scalers=False,
        )
        targets = model.consumption_scaler.transform(
            consumption.reshape(-1, 1)
        ).flatten()
        X, y = model.create_sequences(features, targets)

        split_idx = int(len(X) * 0.8)
        X_val, y_val = X[split_idx:], y[split_idx:]
        if len(y_val) < 3:
            return None

        preds = model.predict_batch(X_val)
        actual = model.consumption_scaler.inverse_transform(
            y_val.reshape(-1, 1)
        ).flatten()
        hybrid_metrics = _core_metrics(
            ForecastingMetrics.calculate_all_metrics(actual, preds)
        )

        val_start = split_idx + model.sequence_length
        train_series = consumption[:val_start]
        test_series = consumption[val_start:val_start + len(y_val)]

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
                "validation_days": int(len(test_series)),
                "validation_start_index": int(val_start),
            },
            "source": "ops_model_live_evaluation",
        }
    except Exception as e:
        print(f"[!] Ops baseline comparison failed: {e}")
        return None


@app.on_event("startup")
async def startup_event():
    _try_load_ops_model()


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
        "ops_integration": {
            "auto_loads": "models/ops/daily (trained by examples/daily_update.py)",
            "forecast_endpoint": "GET /ops/forecast",
        },
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
        model_state["source"] = "in_memory"
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
    """Return latest hybrid-vs-ARIMA comparison.

    Prefers the in-memory comparison from the last /train-daily run;
    falls back to a live evaluation of the operational model on the
    current anchored data so the comparison matrix stays available.
    """
    if not model_state["is_trained"]:
        raise HTTPException(
            status_code=400,
            detail="Model not trained. Run /train-daily or examples/daily_update.py first.",
        )
    comparison = model_state.get("baseline_comparison")
    source = "training_run"
    if comparison is None:
        comparison = _hybrid_vs_arima_from_ops()
        source = comparison.get("source", "ops_model_live_evaluation") if comparison else None
    return {
        "status": "success",
        "baseline_comparison": comparison,
        "comparison_source": source,
        "last_trained": model_state.get("last_trained"),
    }


def _slice_forecast(forecast: dict, days: int) -> dict:
    """Trim a stored forecast payload to the requested horizon."""
    out = dict(forecast)
    for key in (
        "dates", "predictions_kwh", "lower95_kwh", "upper95_kwh", "cost_php",
        "has_classes", "temperature", "humidity", "rainfall", "anomaly_flags",
    ):
        values = out.get(key)
        if isinstance(values, list) and len(values) > days:
            out[key] = values[:days]
    out["forecast_days"] = int(days)
    if isinstance(out.get("predictions_kwh"), list):
        out["total_consumption_kwh"] = float(np.sum(out["predictions_kwh"]))
    if isinstance(out.get("cost_php"), list):
        out["total_cost_php"] = float(np.sum(out["cost_php"]))
    return out


@app.get("/ops/forecast")
async def ops_forecast(days: int = 0, refresh: bool = False):
    """Latest operational forecast from the daily update pipeline.

    By default returns the stored artifact produced by
    examples/daily_update.py (data/processed/ops/latest_forecast.json),
    trimmed to the requested horizon. Pass refresh=true (or request more
    days than stored) to recompute live from the ops model, the ops
    dataset, and the current Open-Meteo weather forecast.
    """
    stored = _read_json(LATEST_FORECAST_PATH)
    n_stored = len((stored or {}).get("predictions_kwh", []))

    # Shorter horizon than stored: serve the stored prefix.
    if stored is not None and days and 0 < days <= n_stored:
        return {
            "status": "success",
            "source": "stored",
            "ops_state": _ops_summary(),
            "forecast": _slice_forecast(stored, days),
        }

    if refresh or stored is None or (days and days > n_stored):
        try:
            n_days = max(int(days), 1) if days else int(
                (stored or {}).get("forecast_days", 7)
            )
            payload = _ops_forecast_payload(n_days)
            return {
                "status": "success",
                "source": "refreshed",
                "ops_state": _ops_summary(),
                "forecast": payload,
            }
        except HTTPException:
            if stored is None:
                raise
        except Exception as e:
            if stored is None:
                raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "source": "stored",
        "ops_state": _ops_summary(),
        "forecast": stored,
    }


@app.get("/model-status")
async def model_status():
    """Get current model status."""
    training_snapshot = model_state.get("training_snapshot")
    if training_snapshot is None and model_state.get("source") == "ops_disk":
        training_snapshot = _ops_training_snapshot()
    return {
        "is_trained": model_state["is_trained"],
        "last_trained": model_state["last_trained"],
        "model_type": "Enhanced LSTM-SVM Hybrid",
        "model_source": model_state.get("source"),
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
        "training_days": int(len(training_snapshot.get("consumption", []))) if training_snapshot else 0,
        "ops": _ops_summary(),
        "runtime": {
            "uses_tensorflow_lstm": bool(HAS_TF),
            "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
        },
    }


@app.get("/metrics")
async def metrics_snapshot():
    """Compatibility endpoint for analytics view.

    Returns latest validation metrics when available. When the model was
    auto-loaded from the operational pipeline, the training snapshot is
    built from the anchored rows of data/daily_ops_dataset.csv so the
    frontend hydration and models.html comparison matrix receive real
    historical data.
    """
    if not model_state["is_trained"]:
        return {
            "status": "not_trained",
            "is_trained": False,
            "validation_metrics": None,
            "baseline_comparison": None,
            "training_snapshot": None,
            "last_trained": model_state.get("last_trained"),
            "model_source": model_state.get("source"),
            "ops": _ops_summary(),
            "runtime": {
                "uses_tensorflow_lstm": bool(HAS_TF),
                "lstm_backend": "tensorflow_lstm" if HAS_TF else "fallback_mlp",
            },
        }

    training_snapshot = model_state.get("training_snapshot")
    if training_snapshot is None and model_state.get("source") == "ops_disk":
        training_snapshot = _ops_training_snapshot()

    return {
        "status": "success",
        "is_trained": True,
        "validation_metrics": model_state.get("validation_metrics"),
        "baseline_comparison": model_state.get("baseline_comparison"),
        "training_snapshot": training_snapshot,
        "last_trained": model_state.get("last_trained"),
        "model_source": model_state.get("source"),
        "ops": _ops_summary(),
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
