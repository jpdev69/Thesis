"""ARIMA baseline model for thesis objective benchmarking."""

import numpy as np

from src.evaluation.metrics import ForecastingMetrics

try:
    from statsmodels.tsa.arima.model import ARIMA
    HAS_STATSMODELS = True
except Exception:
    HAS_STATSMODELS = False


class ARIMABaseline:
    """Classical ARIMA baseline for comparison with hybrid models."""

    def __init__(self, candidate_orders=None):
        self.candidate_orders = candidate_orders or [
            (1, 0, 0),
            (2, 0, 0),
            (1, 1, 0),
            (0, 1, 1),
            (1, 1, 1),
            (2, 1, 1),
        ]
        self.selected_order = None
        self.used_fallback = False
        self.fallback_reason = None

    def _fit_arima(self, series, order):
        model = ARIMA(
            series,
            order=order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        return model.fit(method_kwargs={"warn_convergence": False})

    def _select_best_order(self, train_series):
        best_order = None
        best_aic = np.inf

        for order in self.candidate_orders:
            try:
                result = self._fit_arima(train_series, order)
                if np.isfinite(result.aic) and result.aic < best_aic:
                    best_aic = result.aic
                    best_order = order
            except Exception:
                continue

        return best_order or (1, 1, 1)

    def _naive_forecast(self, train_series, horizon):
        self.used_fallback = True
        self.fallback_reason = "naive_last_value"
        return np.repeat(float(train_series[-1]), horizon)

    def forecast(self, train_series, horizon):
        train_series = np.array(train_series, dtype=np.float64)
        horizon = int(horizon)

        self.used_fallback = False
        self.fallback_reason = None
        self.selected_order = None

        if horizon <= 0:
            return np.array([], dtype=np.float64)

        if len(train_series) < 12:
            return self._naive_forecast(train_series, horizon)

        if np.std(train_series) == 0:
            return self._naive_forecast(train_series, horizon)

        if not HAS_STATSMODELS:
            self.used_fallback = True
            self.fallback_reason = "statsmodels_not_installed"
            return self._naive_forecast(train_series, horizon)

        self.selected_order = self._select_best_order(train_series)

        try:
            result = self._fit_arima(train_series, self.selected_order)
            forecast = result.forecast(steps=horizon)
            return np.array(forecast, dtype=np.float64)
        except Exception:
            return self._naive_forecast(train_series, horizon)

    def evaluate(self, train_series, test_series):
        test_series = np.array(test_series, dtype=np.float64)
        preds = self.forecast(train_series, len(test_series))

        full_metrics = ForecastingMetrics.calculate_all_metrics(test_series, preds)
        core_metrics = {
            "RMSE": float(full_metrics["RMSE"]),
            "MAE": float(full_metrics["MAE"]),
            "MAPE": float(full_metrics["MAPE"]),
            "R2": float(full_metrics["R2"]),
        }

        return {
            "metrics": core_metrics,
            "full_metrics": full_metrics,
            "order": list(self.selected_order) if self.selected_order else None,
            "used_fallback": bool(self.used_fallback),
            "fallback_reason": self.fallback_reason,
            "predictions": preds,
        }
