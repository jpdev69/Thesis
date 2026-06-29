"""Comprehensive evaluation metrics for forecasting models"""

import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


class ForecastingMetrics:
    """Extensive metrics for energy forecasting evaluation including
    directional accuracy, peak error, Theil's U, and forecast bias."""
    
    @staticmethod
    def calculate_all_metrics(y_true, y_pred):
        """Calculate all relevant metrics.
        
        Returns:
            dict of metric name -> value
        """
        y_true = np.array(y_true, dtype=np.float64)
        y_pred = np.array(y_pred, dtype=np.float64)
        
        metrics = {
            'MSE': float(mean_squared_error(y_true, y_pred)),
            'RMSE': float(np.sqrt(mean_squared_error(y_true, y_pred))),
            'MAE': float(mean_absolute_error(y_true, y_pred)),
            'MAPE': ForecastingMetrics.mape(y_true, y_pred),
            'R2': float(r2_score(y_true, y_pred)),
            'SMAPE': ForecastingMetrics.smape(y_true, y_pred),
            'DirectionalAccuracy': ForecastingMetrics.directional_accuracy(y_true, y_pred),
            'PeakError': ForecastingMetrics.peak_error(y_true, y_pred),
            'TheilU': ForecastingMetrics.theils_u(y_true, y_pred),
            'ForecastBias': ForecastingMetrics.forecast_bias(y_true, y_pred),
            'NRMSE': ForecastingMetrics.nrmse(y_true, y_pred),
            'MaxError': float(np.max(np.abs(y_true - y_pred)))
        }
        return metrics
    
    @staticmethod
    def mape(y_true, y_pred):
        """Mean Absolute Percentage Error."""
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        mask = y_true != 0
        if not np.any(mask):
            return 0.0
        return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    
    @staticmethod
    def smape(y_true, y_pred):
        """Symmetric Mean Absolute Percentage Error."""
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
        mask = denominator != 0
        if not np.any(mask):
            return 0.0
        return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / denominator[mask]) * 100)
    
    @staticmethod
    def directional_accuracy(y_true, y_pred):
        """Percentage of correct direction predictions.
        
        Measures how often the model correctly predicts whether the
        value will go up or down relative to the previous observation.
        """
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        if len(y_true) < 2:
            return 0.0
        
        true_direction = np.diff(y_true) > 0
        pred_direction = np.diff(y_pred) > 0
        
        return float(np.mean(true_direction == pred_direction) * 100)
    
    @staticmethod
    def peak_error(y_true, y_pred):
        """Error at peak demand point.
        
        The absolute percentage error at the time of actual peak consumption.
        Critical for capacity planning.
        """
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        peak_idx = np.argmax(y_true)
        peak_actual = y_true[peak_idx]
        peak_predicted = y_pred[peak_idx]
        
        if peak_actual == 0:
            return 0.0
        return float(abs(peak_actual - peak_predicted) / peak_actual * 100)
    
    @staticmethod
    def theils_u(y_true, y_pred):
        """Theil's U statistic.
        
        U < 1: Forecast is better than naive (random walk)
        U = 1: Forecast is same as naive
        U > 1: Forecast is worse than naive
        """
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        
        if len(y_true) < 2:
            return 1.0
        
        # Naive forecast = previous value
        naive_pred = np.roll(y_true, 1)
        naive_pred[0] = y_true[0]
        
        forecast_mse = np.mean((y_true[1:] - y_pred[1:]) ** 2)
        naive_mse = np.mean((y_true[1:] - naive_pred[1:]) ** 2)
        
        if naive_mse == 0:
            return 0.0
        
        return float(np.sqrt(forecast_mse / naive_mse))
    
    @staticmethod
    def forecast_bias(y_true, y_pred):
        """Forecast bias (systematic over/under prediction).
        
        Positive = systematic over-prediction
        Negative = systematic under-prediction
        Near 0 = unbiased
        """
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        mean_actual = np.mean(y_true)
        if mean_actual == 0:
            return 0.0
        return float(np.mean(y_pred - y_true) / mean_actual * 100)
    
    @staticmethod
    def nrmse(y_true, y_pred):
        """Normalized RMSE (as percentage of mean)."""
        y_true, y_pred = np.array(y_true, dtype=np.float64), np.array(y_pred, dtype=np.float64)
        mean_actual = np.mean(y_true)
        if mean_actual == 0:
            return 0.0
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        return float(rmse / mean_actual * 100)
    
    @staticmethod
    def confidence_interval_coverage(y_true, y_lower, y_upper):
        """Percentage of actual values falling within confidence interval.
        
        Good model: coverage ≈ nominal level (e.g., ~95% for 95% CI)
        """
        y_true = np.array(y_true, dtype=np.float64)
        y_lower = np.array(y_lower, dtype=np.float64)
        y_upper = np.array(y_upper, dtype=np.float64)
        
        within = (y_true >= y_lower) & (y_true <= y_upper)
        return float(np.mean(within) * 100)
    
    @staticmethod
    def compare_models(results_dict):
        """Compare metrics across multiple models.
        
        Args:
            results_dict: {model_name: {metric_name: value, ...}, ...}
        
        Returns:
            dict with 'comparison' table and 'best_model' per metric
        """
        if not results_dict:
            return {'comparison': {}, 'best_model': {}}
        
        all_metrics = set()
        for metrics in results_dict.values():
            all_metrics.update(metrics.keys())
        
        # Lower is better for these metrics
        lower_better = {'MSE', 'RMSE', 'MAE', 'MAPE', 'SMAPE', 'PeakError', 
                        'TheilU', 'NRMSE', 'MaxError'}
        # Closer to 0 is better
        zero_better = {'ForecastBias'}
        
        best_model = {}
        for metric in all_metrics:
            values = {name: metrics.get(metric) for name, metrics in results_dict.items() 
                      if metric in metrics}
            
            if not values:
                continue
            
            if metric in lower_better:
                best_model[metric] = min(values, key=values.get)
            elif metric in zero_better:
                best_model[metric] = min(values, key=lambda k: abs(values[k]))
            else:
                best_model[metric] = max(values, key=values.get)
        
        return {
            'comparison': results_dict,
            'best_model': best_model
        }
    
    @staticmethod
    def generate_report(metrics, model_name="Model"):
        """Generate a formatted performance report string.
        
        Args:
            metrics: Dict of metric name -> value
            model_name: Name of the model
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"  FORECASTING PERFORMANCE REPORT: {model_name}")
        lines.append("=" * 60)
        
        # Group metrics
        accuracy = {k: v for k, v in metrics.items() 
                    if k in ('RMSE', 'MAE', 'MAPE', 'SMAPE', 'R2', 'NRMSE')}
        quality = {k: v for k, v in metrics.items() 
                   if k in ('DirectionalAccuracy', 'PeakError', 'TheilU', 'ForecastBias')}
        other = {k: v for k, v in metrics.items() 
                 if k not in accuracy and k not in quality}
        
        if accuracy:
            lines.append("\n  📊 Accuracy Metrics:")
            for name, value in accuracy.items():
                if isinstance(value, float):
                    lines.append(f"    {name:25s}: {value:12.4f}")
                else:
                    lines.append(f"    {name:25s}: {value}")
        
        if quality:
            lines.append("\n  🎯 Quality Metrics:")
            for name, value in quality.items():
                if isinstance(value, float):
                    lines.append(f"    {name:25s}: {value:12.4f}")
                    # Add interpretation
                    if name == 'TheilU':
                        interp = "✓ Better than naive" if value < 1 else "✗ Worse than naive"
                        lines.append(f"    {'':25s}  ({interp})")
                    elif name == 'DirectionalAccuracy':
                        interp = "✓ Good" if value > 60 else "⚠ Poor"
                        lines.append(f"    {'':25s}  ({interp})")
                else:
                    lines.append(f"    {name:25s}: {value}")
        
        if other:
            lines.append("\n  📈 Other Metrics:")
            for name, value in other.items():
                if isinstance(value, float):
                    lines.append(f"    {name:25s}: {value:12.4f}")
                else:
                    lines.append(f"    {name:25s}: {value}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    @staticmethod
    def print_metrics(metrics, model_name="Model"):
        """Pretty print metrics."""
        print(ForecastingMetrics.generate_report(metrics, model_name))
