"""
Enhanced Daily Campus Electricity Prediction Model
Predicts daily electricity consumption based on:
- Historical consumption patterns
- Weather conditions (temperature, humidity, rainfall)
- Campus schedule (class days vs no-class days)
- Day of week patterns
- Holiday/special event detection  
- Seasonal patterns (month/quarter)
- Anomaly detection and flagging
- Peak load estimation
"""

import os
import numpy as np
import joblib
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta


# Philippine public holidays (month, day)
PH_HOLIDAYS = [
    (1, 1),    # New Year's Day
    (2, 25),   # EDSA Revolution Anniversary
    (4, 9),    # Araw ng Kagitingan
    (5, 1),    # Labor Day
    (6, 12),   # Independence Day
    (8, 21),   # Ninoy Aquino Day
    (8, 28),   # National Heroes Day (approx)
    (11, 1),   # All Saints' Day
    (11, 30),  # Bonifacio Day
    (12, 25),  # Christmas Day
    (12, 30),  # Rizal Day
    (12, 31),  # Last Day of the Year
]


def is_philippine_holiday(date):
    """Check if a date is a Philippine public holiday."""
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')
    return (date.month, date.day) in PH_HOLIDAYS


class DailyEnergyPredictor:
    """Enhanced LSTM-SVM model for daily electricity prediction
    with weather awareness, schedule awareness, anomaly detection,
    and peak load estimation."""
    
    def __init__(self, sequence_length=7, lstm_weight=0.7, 
                 anomaly_threshold=2.0):
        """
        Args:
            sequence_length: Number of past days to consider (default: 7)
            lstm_weight: Weight for LSTM predictions (0.7 = 70% LSTM, 30% SVM)
            anomaly_threshold: Z-score threshold for anomaly detection
        """
        self.sequence_length = sequence_length
        self.lstm_weight = lstm_weight
        self.svm_weight = 1 - lstm_weight
        self.anomaly_threshold = anomaly_threshold
        
        self.consumption_scaler = StandardScaler()
        self.weather_scaler = StandardScaler()
        self.lstm_model = None
        self.svm_model = None
        self.is_trained = False
        
        # Statistics for anomaly detection
        self.consumption_mean = None
        self.consumption_std = None
        self.weekday_means = {}
        self.class_day_mean = None
        self.no_class_day_mean = None
    
    def _build_lstm_model(self, n_features):
        """Build Enhanced LSTM with Multi-Head Attention."""
        inputs = keras.Input(shape=(self.sequence_length, n_features))
        
        # First LSTM layer with residual
        lstm1 = layers.LSTM(128, return_sequences=True,
                           kernel_regularizer=keras.regularizers.l2(1e-4))(inputs)
        lstm1 = layers.LayerNormalization(epsilon=1e-6)(lstm1)
        lstm1 = layers.Dropout(0.3)(lstm1)
        
        # Second LSTM layer
        lstm2 = layers.LSTM(64, return_sequences=True,
                           kernel_regularizer=keras.regularizers.l2(1e-4))(lstm1)
        lstm2 = layers.LayerNormalization(epsilon=1e-6)(lstm2)
        lstm2 = layers.Dropout(0.3)(lstm2)
        
        # Multi-head attention
        attention_output = layers.MultiHeadAttention(
            num_heads=4, key_dim=16
        )(lstm2, lstm2)
        attention_output = layers.Dropout(0.2)(attention_output)
        attention_output = layers.Add()([lstm2, attention_output])
        attention_output = layers.LayerNormalization(epsilon=1e-6)(attention_output)
        
        # Global pooling
        context = layers.GlobalAveragePooling1D()(attention_output)
        
        # Dense layers
        dense1 = layers.Dense(64, activation='gelu')(context)
        dense1 = layers.Dropout(0.2)(dense1)
        dense2 = layers.Dense(32, activation='gelu')(dense1)
        dense2 = layers.Dropout(0.1)(dense2)
        outputs = layers.Dense(1)(dense2)
        
        model = keras.Model(inputs=inputs, outputs=outputs)
        
        lr_schedule = keras.optimizers.schedules.CosineDecay(
            initial_learning_rate=0.001, decay_steps=2000, alpha=1e-6
        )
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=lr_schedule),
            loss='huber',
            metrics=['mae', 'mape']
        )
        
        return model
    
    def prepare_features(self, consumption, temperature, humidity, rainfall, 
                        has_classes, day_of_week, is_weekend, 
                        dates=None, fit_scalers=True):
        """Prepare enhanced feature matrix with seasonal and holiday features.
        
        Args:
            consumption: Daily electricity consumption (kWh or ₱)
            temperature: Daily average temperature (°C)
            humidity: Daily average humidity (%)
            rainfall: Daily rainfall (mm)
            has_classes: 1 if classes, 0 if no classes
            day_of_week: 0=Monday, 6=Sunday
            is_weekend: 1 if weekend, 0 if weekday
            dates: Optional list of date strings for holiday detection
            fit_scalers: Whether to fit scalers (True for training)
        
        Returns:
            Feature matrix with shape (n_samples, n_features)
        """
        consumption = np.array(consumption, dtype=np.float64)
        temperature = np.array(temperature, dtype=np.float64)
        humidity = np.array(humidity, dtype=np.float64)
        rainfall = np.array(rainfall, dtype=np.float64)
        has_classes = np.array(has_classes, dtype=np.float64)
        day_of_week = np.array(day_of_week, dtype=np.float64)
        is_weekend = np.array(is_weekend, dtype=np.float64)
        
        # Normalize consumption
        if fit_scalers:
            consumption_norm = self.consumption_scaler.fit_transform(
                consumption.reshape(-1, 1)
            ).flatten()
        else:
            consumption_norm = self.consumption_scaler.transform(
                consumption.reshape(-1, 1)
            ).flatten()
        
        # Normalize weather features
        weather_features = np.column_stack([temperature, humidity, rainfall])
        if fit_scalers:
            weather_norm = self.weather_scaler.fit_transform(weather_features)
        else:
            weather_norm = self.weather_scaler.transform(weather_features)
        
        # Cyclical encoding for day of week
        day_sin = np.sin(2 * np.pi * day_of_week / 7)
        day_cos = np.cos(2 * np.pi * day_of_week / 7)
        
        # Month/seasonal encoding (estimate from sequential data)
        n = len(consumption)
        if dates is not None:
            months = np.array([datetime.strptime(d, '%Y-%m-%d').month for d in dates], dtype=np.float64)
            is_holiday = np.array([float(is_philippine_holiday(d)) for d in dates])
        else:
            months = np.ones(n) * 6  # Default to middle of year
            is_holiday = np.zeros(n)
        
        month_sin = np.sin(2 * np.pi * months / 12)
        month_cos = np.cos(2 * np.pi * months / 12)
        
        # Rolling statistics (7-day window)
        rolling_mean = np.convolve(consumption_norm, np.ones(7) / 7, mode='same')
        rolling_std = np.array([
            np.std(consumption_norm[max(0, i-3):i+4]) 
            for i in range(n)
        ])
        
        # Rate of change
        rate_of_change = np.diff(consumption_norm, prepend=consumption_norm[0])
        
        # Lag features
        lag_1 = np.roll(consumption_norm, 1)
        lag_1[0] = consumption_norm[0]
        lag_7 = np.roll(consumption_norm, 7)
        lag_7[:7] = consumption_norm[0]
        
        # Combine all features
        features = np.column_stack([
            consumption_norm,      # Normalized consumption
            weather_norm[:, 0],    # Normalized temperature
            weather_norm[:, 1],    # Normalized humidity
            weather_norm[:, 2],    # Normalized rainfall
            has_classes,           # Binary: has classes or not
            is_weekend,            # Binary: weekend or not
            day_sin,               # Cyclical day encoding
            day_cos,               # Cyclical day encoding
            month_sin,             # Cyclical month encoding
            month_cos,             # Cyclical month encoding
            is_holiday,            # Binary: holiday or not
            rolling_mean,          # 7-day rolling mean
            rolling_std,           # 7-day rolling std
            rate_of_change,        # Day-over-day change
            lag_1,                 # 1-day lag
            lag_7                  # 7-day lag
        ])
        
        return features
    
    def create_sequences(self, features, targets):
        """Create sequences for time series prediction."""
        X, y = [], []
        for i in range(len(features) - self.sequence_length):
            X.append(features[i:i + self.sequence_length])
            y.append(targets[i + self.sequence_length])
        
        return np.array(X), np.array(y)
    
    def detect_anomalies(self, consumption, dates=None):
        """Detect anomalous consumption days using Z-score method.
        
        Returns:
            list of dicts with 'index', 'date', 'value', 'z_score', 'type'
        """
        consumption = np.array(consumption, dtype=np.float64)
        mean = np.mean(consumption)
        std = np.std(consumption)
        
        if std == 0:
            return []
        
        anomalies = []
        for i, val in enumerate(consumption):
            z_score = (val - mean) / std
            if abs(z_score) > self.anomaly_threshold:
                anomaly = {
                    'index': i,
                    'value': float(val),
                    'z_score': float(z_score),
                    'expected': float(mean),
                    'deviation_pct': float((val - mean) / mean * 100),
                    'type': 'spike' if z_score > 0 else 'dip'
                }
                if dates is not None and i < len(dates):
                    anomaly['date'] = dates[i]
                anomalies.append(anomaly)
        
        return anomalies
    
    def estimate_peak_load(self, predictions, dates=None):
        """Estimate peak load from predictions.
        
        Returns:
            dict with peak analysis information
        """
        predictions = np.array(predictions)
        peak_idx = np.argmax(predictions)
        min_idx = np.argmin(predictions)
        
        result = {
            'peak_value': float(predictions[peak_idx]),
            'peak_day_index': int(peak_idx),
            'min_value': float(predictions[min_idx]),
            'min_day_index': int(min_idx),
            'avg_load': float(np.mean(predictions)),
            'load_factor': float(np.mean(predictions) / predictions[peak_idx]) if predictions[peak_idx] > 0 else 0,
            'range': float(predictions[peak_idx] - predictions[min_idx])
        }
        
        if dates is not None:
            if peak_idx < len(dates):
                result['peak_date'] = dates[peak_idx]
            if min_idx < len(dates):
                result['min_date'] = dates[min_idx]
        
        return result
    
    def train(self, consumption, temperature, humidity, rainfall,
              has_classes, day_of_week, is_weekend, dates=None,
              epochs=100, validation_split=0.2):
        """Train the hybrid LSTM-SVM model.
        
        Args:
            consumption: Array of daily consumption values
            temperature: Array of daily temperatures
            humidity: Array of daily humidity values
            rainfall: Array of daily rainfall
            has_classes: Array of class indicators (1=classes, 0=no classes)
            day_of_week: Array of day numbers (0-6)
            is_weekend: Array of weekend indicators (1=weekend, 0=weekday)
            dates: Optional array of date strings
            epochs: Number of training epochs
            validation_split: Fraction of data for validation
        """
        consumption = np.array(consumption, dtype=np.float64)
        
        print("Preparing features...")
        
        # Store statistics for anomaly detection
        self.consumption_mean = float(np.mean(consumption))
        self.consumption_std = float(np.std(consumption))
        
        # Per-weekday means
        day_of_week_arr = np.array(day_of_week)
        for d in range(7):
            mask = day_of_week_arr == d
            if np.any(mask):
                self.weekday_means[d] = float(np.mean(consumption[mask]))
        
        has_classes_arr = np.array(has_classes)
        class_mask = has_classes_arr == 1
        no_class_mask = has_classes_arr == 0
        if np.any(class_mask):
            self.class_day_mean = float(np.mean(consumption[class_mask]))
        if np.any(no_class_mask):
            self.no_class_day_mean = float(np.mean(consumption[no_class_mask]))
        
        # Prepare features
        features = self.prepare_features(
            consumption, temperature, humidity, rainfall,
            has_classes, day_of_week, is_weekend, dates, fit_scalers=True
        )
        
        # Normalize targets
        targets = self.consumption_scaler.transform(consumption.reshape(-1, 1)).flatten()
        
        # Create sequences
        X, y = self.create_sequences(features, targets)
        
        print(f"Created {len(X)} training sequences")
        print(f"Feature shape: {X.shape} ({X.shape[2]} features per timestep)")
        
        # Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Build and train LSTM
        print("\nTraining LSTM component...")
        n_features = X.shape[2]
        self.lstm_model = self._build_lstm_model(n_features)
        
        callbacks = [
            keras.callbacks.EarlyStopping(
                patience=15, restore_best_weights=True, monitor='val_loss'
            ),
            keras.callbacks.ReduceLROnPlateau(
                factor=0.5, patience=7, monitor='val_loss', min_lr=1e-7
            ),
            keras.callbacks.TerminateOnNaN()
        ]
        
        history = self.lstm_model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=min(32, len(X_train)),
            callbacks=callbacks,
            verbose=1
        )
        
        # Get LSTM predictions for SVM training
        print("\nTraining SVM component...")
        lstm_train_pred = self.lstm_model.predict(X_train, verbose=0).flatten()
        
        # Prepare SVM features
        X_train_flat = X_train.reshape(X_train.shape[0], -1)
        X_svm = np.column_stack([X_train_flat, lstm_train_pred])
        
        # Train SVM
        self.svm_model = SVR(kernel='rbf', C=100, epsilon=0.01, gamma='scale')
        self.svm_model.fit(X_svm, y_train)
        
        self.is_trained = True
        
        # Evaluate on validation set
        print("\nEvaluating model...")
        val_predictions = self.predict_batch(X_val)
        y_val_actual = self.consumption_scaler.inverse_transform(
            y_val.reshape(-1, 1)
        ).flatten()
        
        rmse = np.sqrt(np.mean((y_val_actual - val_predictions) ** 2))
        mae = np.mean(np.abs(y_val_actual - val_predictions))
        mask = y_val_actual != 0
        mape = np.mean(np.abs((y_val_actual[mask] - val_predictions[mask]) / y_val_actual[mask])) * 100
        
        # R² score
        ss_res = np.sum((y_val_actual - val_predictions) ** 2)
        ss_tot = np.sum((y_val_actual - np.mean(y_val_actual)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Directional accuracy
        if len(y_val_actual) > 1:
            actual_direction = np.diff(y_val_actual) > 0
            pred_direction = np.diff(val_predictions) > 0
            directional_acc = np.mean(actual_direction == pred_direction) * 100
        else:
            directional_acc = 0
        
        print(f"\nValidation Metrics:")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  MAE: {mae:.2f}")
        print(f"  MAPE: {mape:.2f}%")
        print(f"  R²: {r2:.4f}")
        print(f"  Directional Accuracy: {directional_acc:.1f}%")
        
        # Detect anomalies in historical data
        anomalies = self.detect_anomalies(consumption, dates)
        if anomalies:
            print(f"\n⚠ Detected {len(anomalies)} anomalous day(s) in historical data")
        
        self.validation_metrics = {
            'RMSE': float(rmse),
            'MAE': float(mae),
            'MAPE': float(mape),
            'R2': float(r2),
            'directional_accuracy': float(directional_acc),
            'anomalies_found': len(anomalies)
        }
        
        return history
    
    def predict_batch(self, X):
        """Predict for multiple sequences (raw normalized output)."""
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        # LSTM predictions
        lstm_pred = self.lstm_model.predict(X, verbose=0).flatten()
        
        # SVM predictions
        X_flat = X.reshape(X.shape[0], -1)
        X_svm = np.column_stack([X_flat, lstm_pred])
        svm_pred = self.svm_model.predict(X_svm)
        
        # Weighted ensemble
        hybrid_pred = (self.lstm_weight * lstm_pred + self.svm_weight * svm_pred)
        
        # Denormalize
        predictions = self.consumption_scaler.inverse_transform(
            hybrid_pred.reshape(-1, 1)
        ).flatten()
        
        return predictions
    
    def predict_with_confidence(self, X, n_forward=30):
        """Predict with confidence intervals.
        
        Returns:
            dict with 'mean', 'lower', 'upper', 'std' (all denormalized)
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        # MC Dropout predictions
        all_preds = []
        for _ in range(n_forward):
            lstm_pred = self.lstm_model.model(X, training=True).numpy().flatten()
            X_flat = X.reshape(X.shape[0], -1)
            X_svm = np.column_stack([X_flat, lstm_pred])
            svm_pred = self.svm_model.predict(X_svm)
            hybrid = self.lstm_weight * lstm_pred + self.svm_weight * svm_pred
            all_preds.append(hybrid)
        
        all_preds = np.array(all_preds)
        
        mean_pred = self.consumption_scaler.inverse_transform(
            np.mean(all_preds, axis=0).reshape(-1, 1)
        ).flatten()
        
        std_pred_norm = np.std(all_preds, axis=0)
        lower = self.consumption_scaler.inverse_transform(
            np.percentile(all_preds, 2.5, axis=0).reshape(-1, 1)
        ).flatten()
        upper = self.consumption_scaler.inverse_transform(
            np.percentile(all_preds, 97.5, axis=0).reshape(-1, 1)
        ).flatten()
        
        return {
            'mean': mean_pred,
            'lower': lower,
            'upper': upper,
            'std': (upper - lower) / 3.92  # Approximate std
        }
    
    def predict_single_day(self, past_consumption, past_temperature, past_humidity,
                          past_rainfall, past_has_classes, past_day_of_week,
                          past_is_weekend, next_temperature, next_humidity,
                          next_rainfall, next_has_classes, next_day_of_week,
                          next_is_weekend):
        """Predict electricity consumption for a single day."""
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        # Prepare past features
        past_features = self.prepare_features(
            past_consumption, past_temperature, past_humidity,
            past_rainfall, past_has_classes, past_day_of_week,
            past_is_weekend, fit_scalers=False
        )
        
        # Take last sequence_length days
        sequence = past_features[-self.sequence_length:]
        X = sequence.reshape(1, self.sequence_length, -1)
        
        prediction = self.predict_batch(X)[0]
        return prediction
    
    def predict_next_n_days(self, past_data, future_weather, future_schedule, n_days=7):
        """Predict electricity consumption for next N days with confidence.
        
        Args:
            past_data: Dict with keys: consumption, temperature, humidity, rainfall,
                      has_classes, day_of_week, is_weekend (arrays of past 7+ days)
            future_weather: Dict with keys: temperature, humidity, rainfall (arrays of N days)
            future_schedule: Dict with keys: has_classes, day_of_week, is_weekend (arrays of N days)
            n_days: Number of days to predict
        
        Returns:
            dict with 'predictions', 'lower', 'upper', 'anomaly_flags', 'peak_analysis'
        """
        predictions = []
        lower_bounds = []
        upper_bounds = []
        
        # Start with past data
        current_consumption = past_data['consumption'].copy()
        current_temperature = past_data['temperature'].copy()
        current_humidity = past_data['humidity'].copy()
        current_rainfall = past_data['rainfall'].copy()
        current_has_classes = past_data['has_classes'].copy()
        current_day_of_week = past_data['day_of_week'].copy()
        current_is_weekend = past_data['is_weekend'].copy()
        
        for day in range(n_days):
            # Build features for current window
            features = self.prepare_features(
                current_consumption[-self.sequence_length:],
                current_temperature[-self.sequence_length:],
                current_humidity[-self.sequence_length:],
                current_rainfall[-self.sequence_length:],
                current_has_classes[-self.sequence_length:],
                current_day_of_week[-self.sequence_length:],
                current_is_weekend[-self.sequence_length:],
                fit_scalers=False
            )
            
            X = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
            
            # Predict with confidence
            conf = self.predict_with_confidence(X, n_forward=20)
            pred = conf['mean'][0]
            
            predictions.append(pred)
            lower_bounds.append(conf['lower'][0])
            upper_bounds.append(conf['upper'][0])
            
            # Update current data with prediction for recursive forecasting
            current_consumption = np.append(current_consumption, pred)
            current_temperature = np.append(current_temperature, future_weather['temperature'][day])
            current_humidity = np.append(current_humidity, future_weather['humidity'][day])
            current_rainfall = np.append(current_rainfall, future_weather['rainfall'][day])
            current_has_classes = np.append(current_has_classes, future_schedule['has_classes'][day])
            current_day_of_week = np.append(current_day_of_week, future_schedule['day_of_week'][day])
            current_is_weekend = np.append(current_is_weekend, future_schedule['is_weekend'][day])
        
        predictions = np.array(predictions)
        
        # Anomaly flags on predictions
        anomaly_flags = []
        if self.consumption_mean is not None and self.consumption_std is not None and self.consumption_std > 0:
            for pred in predictions:
                z = (pred - self.consumption_mean) / self.consumption_std
                anomaly_flags.append(abs(z) > self.anomaly_threshold)
        else:
            anomaly_flags = [False] * len(predictions)
        
        # Peak analysis
        peak_analysis = self.estimate_peak_load(predictions)
        
        return {
            'predictions': predictions,
            'lower': np.array(lower_bounds),
            'upper': np.array(upper_bounds),
            'anomaly_flags': anomaly_flags,
            'peak_analysis': peak_analysis
        }
    
    def save(self, directory):
        """Save complete model state."""
        os.makedirs(directory, exist_ok=True)
        if self.lstm_model is not None:
            self.lstm_model.save(os.path.join(directory, 'daily_lstm'))
        if self.svm_model is not None:
            joblib.dump(self.svm_model, os.path.join(directory, 'daily_svm.joblib'))
        joblib.dump({
            'consumption_scaler': self.consumption_scaler,
            'weather_scaler': self.weather_scaler,
            'lstm_weight': self.lstm_weight,
            'svm_weight': self.svm_weight,
            'sequence_length': self.sequence_length,
            'anomaly_threshold': self.anomaly_threshold,
            'consumption_mean': self.consumption_mean,
            'consumption_std': self.consumption_std,
            'weekday_means': self.weekday_means,
            'class_day_mean': self.class_day_mean,
            'no_class_day_mean': self.no_class_day_mean,
            'is_trained': self.is_trained
        }, os.path.join(directory, 'daily_meta.joblib'))
    
    def load(self, directory):
        """Load complete model state."""
        self.lstm_model = keras.models.load_model(os.path.join(directory, 'daily_lstm'))
        self.svm_model = joblib.load(os.path.join(directory, 'daily_svm.joblib'))
        meta = joblib.load(os.path.join(directory, 'daily_meta.joblib'))
        self.consumption_scaler = meta['consumption_scaler']
        self.weather_scaler = meta['weather_scaler']
        self.lstm_weight = meta['lstm_weight']
        self.svm_weight = meta['svm_weight']
        self.sequence_length = meta['sequence_length']
        self.anomaly_threshold = meta['anomaly_threshold']
        self.consumption_mean = meta['consumption_mean']
        self.consumption_std = meta['consumption_std']
        self.weekday_means = meta['weekday_means']
        self.class_day_mean = meta['class_day_mean']
        self.no_class_day_mean = meta['no_class_day_mean']
        self.is_trained = meta['is_trained']
