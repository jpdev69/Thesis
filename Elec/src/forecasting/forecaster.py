"""Advanced forecasting engine with ensemble methods, probabilistic output, and decomposition"""

import numpy as np
from typing import Dict, List, Optional


class EnergyForecaster:
    """Multi-step ahead energy demand forecaster with ensemble methods,
    probabilistic output, adaptive horizon, and trend decomposition."""
    
    def __init__(self, model, preprocessor):
        self.model = model
        self.preprocessor = preprocessor
        self.forecast_history = []
    
    def forecast_single_step(self, X):
        """Single step ahead forecast."""
        predictions = self.model.predict(X)
        return self.preprocessor.denormalize(predictions)
    
    def forecast_multi_step(self, initial_sequence, steps=24):
        """Multi-step ahead forecast using recursive strategy."""
        current_sequence = initial_sequence.copy()
        predictions = []
        
        for _ in range(steps):
            next_pred = self.model.predict(current_sequence.reshape(1, -1, 1))
            pred_val = next_pred[0, 0] if next_pred.ndim > 1 else next_pred[0]
            predictions.append(pred_val)
            current_sequence = np.append(current_sequence[1:], pred_val)
        
        predictions = np.array(predictions)
        result = self.preprocessor.denormalize(predictions)
        
        # Store in history
        self.forecast_history.append({
            'steps': steps,
            'predictions': result.tolist()
        })
        
        return result
    
    def forecast_with_confidence(self, X, n_iterations=100):
        """Forecast with confidence intervals using Monte Carlo dropout.
        
        Returns:
            dict with percentiles and mean/std
        """
        predictions = []
        
        for _ in range(n_iterations):
            # Enable dropout during prediction
            if hasattr(self.model, 'model'):
                pred = self.model.model(X, training=True).numpy()
            else:
                pred = self.model.predict(X)
            predictions.append(pred)
        
        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)
        
        return {
            'mean': self.preprocessor.denormalize(mean_pred.flatten()),
            'std': self.preprocessor.denormalize(std_pred.flatten()),
            'lower': self.preprocessor.denormalize((mean_pred - 1.96 * std_pred).flatten()),
            'upper': self.preprocessor.denormalize((mean_pred + 1.96 * std_pred).flatten()),
            'p10': self.preprocessor.denormalize(np.percentile(predictions, 10, axis=0).flatten()),
            'p50': self.preprocessor.denormalize(np.percentile(predictions, 50, axis=0).flatten()),
            'p90': self.preprocessor.denormalize(np.percentile(predictions, 90, axis=0).flatten())
        }
    
    def forecast_multi_step_with_confidence(self, initial_sequence, steps=24, 
                                             n_iterations=50):
        """Multi-step forecast with confidence intervals at each step.
        
        Returns:
            dict with 'mean', 'lower', 'upper', 'p10', 'p50', 'p90' arrays
        """
        all_predictions = []
        
        for _ in range(n_iterations):
            current_sequence = initial_sequence.copy()
            preds = []
            
            for _ in range(steps):
                if hasattr(self.model, 'model'):
                    next_pred = self.model.model(
                        current_sequence.reshape(1, -1, 1), training=True
                    ).numpy()
                else:
                    next_pred = self.model.predict(
                        current_sequence.reshape(1, -1, 1)
                    )
                pred_val = next_pred.flatten()[0]
                preds.append(pred_val)
                current_sequence = np.append(current_sequence[1:], pred_val)
            
            all_predictions.append(preds)
        
        all_predictions = np.array(all_predictions)
        
        return {
            'mean': self.preprocessor.denormalize(np.mean(all_predictions, axis=0)),
            'std': self.preprocessor.denormalize(np.std(all_predictions, axis=0)),
            'lower': self.preprocessor.denormalize(np.percentile(all_predictions, 2.5, axis=0)),
            'upper': self.preprocessor.denormalize(np.percentile(all_predictions, 97.5, axis=0)),
            'p10': self.preprocessor.denormalize(np.percentile(all_predictions, 10, axis=0)),
            'p50': self.preprocessor.denormalize(np.percentile(all_predictions, 50, axis=0)),
            'p90': self.preprocessor.denormalize(np.percentile(all_predictions, 90, axis=0))
        }
    
    def decompose_forecast(self, data, period=7):
        """Decompose time series into trend, seasonal, and residual components.
        
        Uses simple moving average decomposition.
        
        Args:
            data: 1D time series array
            period: Seasonal period (e.g., 7 for weekly, 24 for daily)
            
        Returns:
            dict with 'trend', 'seasonal', 'residual' arrays
        """
        data = np.array(data, dtype=np.float64)
        n = len(data)
        
        # Trend: moving average
        if n >= period:
            trend = np.convolve(data, np.ones(period) / period, mode='same')
        else:
            trend = np.full(n, np.mean(data))
        
        # Detrended data
        detrended = data - trend
        
        # Seasonal pattern: average of each position in the period
        seasonal = np.zeros(n)
        for i in range(n):
            pos = i % period
            same_pos = [detrended[j] for j in range(pos, n, period)]
            seasonal[i] = np.mean(same_pos)
        
        # Residual
        residual = data - trend - seasonal
        
        return {
            'trend': trend,
            'seasonal': seasonal,
            'residual': residual,
            'original': data
        }
    
    def ensemble_forecast(self, models: list, X, weights: Optional[List[float]] = None):
        """Combine predictions from multiple models.
        
        Args:
            models: List of trained model objects with predict() method
            X: Input data
            weights: Optional weights for each model (must sum to 1)
            
        Returns:
            dict with 'ensemble_mean', 'individual_preds', 'spread'
        """
        n_models = len(models)
        
        if weights is None:
            weights = [1.0 / n_models] * n_models
        
        all_preds = []
        for model in models:
            pred = model.predict(X)
            if pred.ndim > 1:
                pred = pred.flatten()
            all_preds.append(pred)
        
        all_preds = np.array(all_preds)
        
        # Weighted ensemble
        weighted_mean = np.zeros_like(all_preds[0])
        for i, (pred, w) in enumerate(zip(all_preds, weights)):
            weighted_mean += w * pred
        
        return {
            'ensemble_mean': self.preprocessor.denormalize(weighted_mean),
            'individual_preds': [self.preprocessor.denormalize(p) for p in all_preds],
            'spread': self.preprocessor.denormalize(np.std(all_preds, axis=0)),
            'weights': weights
        }
    
    def adaptive_horizon(self, data, max_steps=48, quality_threshold=0.15):
        """Automatically determine reliable forecast horizon.
        
        Generates forecasts at increasing horizons and stops when
        uncertainty exceeds the quality threshold.
        
        Args:
            data: Normalized input sequence
            max_steps: Maximum forecast steps
            quality_threshold: Max acceptable coefficient of variation
            
        Returns:
            dict with 'recommended_steps' and 'quality_by_step'
        """
        qualities = []
        
        for steps in range(1, max_steps + 1):
            try:
                result = self.forecast_multi_step_with_confidence(
                    data, steps=steps, n_iterations=20
                )
                # Coefficient of variation at last step
                last_mean = abs(result['mean'][-1])
                last_std = result['std'][-1]
                cv = last_std / last_mean if last_mean > 0 else float('inf')
                qualities.append({'step': steps, 'cv': float(cv)})
                
                if cv > quality_threshold:
                    break
            except Exception:
                break
        
        recommended = len(qualities) if not qualities else qualities[-1]['step'] - 1
        recommended = max(1, min(recommended, max_steps))
        
        return {
            'recommended_steps': recommended,
            'quality_by_step': qualities
        }
