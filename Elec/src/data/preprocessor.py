"""Enhanced data preprocessing utilities with outlier detection, imputation, and feature engineering"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler


class EnergyDataPreprocessor:
    """Comprehensive data preprocessor with outlier detection, missing value
    imputation, rolling statistics, lag features, and robust CSV parsing."""
    
    def __init__(self, sequence_length=24, scaler_type='minmax'):
        self.sequence_length = sequence_length
        self.scaler_type = scaler_type
        
        if scaler_type == 'minmax':
            self.scaler = MinMaxScaler()
        elif scaler_type == 'robust':
            self.scaler = RobustScaler()
        else:
            self.scaler = StandardScaler()
        
        self.fitted = False
        self.data_stats = {}
    
    def create_sequences(self, data, target_col=0):
        """Create sequences for time series forecasting.
        
        Args:
            data: 1D or 2D array of features
            target_col: Column index for target (if 2D)
        
        Returns:
            X: Input sequences
            y: Target values
        """
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i:i + self.sequence_length])
            if data.shape[1] == 1:
                y.append(data[i + self.sequence_length, 0])
            else:
                y.append(data[i + self.sequence_length, target_col])
        
        return np.array(X), np.array(y)
    
    def normalize(self, data):
        """Normalize data using fitted scaler."""
        data_reshaped = data.reshape(-1, 1) if data.ndim == 1 else data
        if not self.fitted:
            normalized = self.scaler.fit_transform(data_reshaped)
            self.fitted = True
        else:
            normalized = self.scaler.transform(data_reshaped)
        
        return normalized.flatten() if data.ndim == 1 else normalized
    
    def denormalize(self, data):
        """Inverse transform normalized data."""
        data_reshaped = data.reshape(-1, 1) if data.ndim == 1 else data
        result = self.scaler.inverse_transform(data_reshaped)
        return result.flatten() if data.ndim == 1 else result
    
    def detect_outliers(self, data, method='iqr', threshold=1.5):
        """Detect outliers using IQR or Z-score method.
        
        Args:
            data: 1D array of values
            method: 'iqr' or 'zscore'
            threshold: IQR multiplier or Z-score threshold
        
        Returns:
            dict with 'mask' (boolean array), 'indices', 'values', 'bounds'
        """
        data = np.array(data, dtype=np.float64)
        
        if method == 'iqr':
            Q1 = np.percentile(data, 25)
            Q3 = np.percentile(data, 75)
            IQR = Q3 - Q1
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            mask = (data < lower_bound) | (data > upper_bound)
        else:  # zscore
            mean = np.mean(data)
            std = np.std(data)
            z_scores = np.abs((data - mean) / std) if std > 0 else np.zeros_like(data)
            mask = z_scores > threshold
            lower_bound = mean - threshold * std
            upper_bound = mean + threshold * std
        
        return {
            'mask': mask,
            'indices': np.where(mask)[0].tolist(),
            'values': data[mask].tolist(),
            'count': int(np.sum(mask)),
            'bounds': {'lower': float(lower_bound), 'upper': float(upper_bound)}
        }
    
    def replace_outliers(self, data, method='iqr', threshold=1.5, strategy='clip'):
        """Replace outliers with clipped or interpolated values.
        
        Args:
            data: 1D array
            method: Detection method ('iqr' or 'zscore')
            threshold: Detection threshold
            strategy: 'clip' (bound to limits) or 'interpolate' (linear)
        
        Returns:
            Cleaned data array
        """
        data = np.array(data, dtype=np.float64).copy()
        result = self.detect_outliers(data, method, threshold)
        
        if strategy == 'clip':
            data = np.clip(data, result['bounds']['lower'], result['bounds']['upper'])
        elif strategy == 'interpolate':
            mask = result['mask']
            if np.any(mask):
                indices = np.arange(len(data))
                valid = ~mask
                if np.sum(valid) >= 2:
                    data[mask] = np.interp(indices[mask], indices[valid], data[valid])
        
        return data
    
    def impute_missing(self, data, method='interpolate'):
        """Handle missing values (NaN/None).
        
        Args:
            data: 1D array (may contain NaN)
            method: 'interpolate', 'forward_fill', 'mean', or 'median'
        
        Returns:
            Imputed data array
        """
        data = np.array(data, dtype=np.float64).copy()
        nan_mask = np.isnan(data)
        
        if not np.any(nan_mask):
            return data
        
        if method == 'interpolate':
            valid = ~nan_mask
            if np.sum(valid) >= 2:
                indices = np.arange(len(data))
                data[nan_mask] = np.interp(indices[nan_mask], indices[valid], data[valid])
            else:
                data[nan_mask] = np.nanmean(data)
        elif method == 'forward_fill':
            for i in range(1, len(data)):
                if nan_mask[i]:
                    data[i] = data[i-1]
            # Back-fill remaining NaNs at start
            for i in range(len(data)-2, -1, -1):
                if np.isnan(data[i]):
                    data[i] = data[i+1]
        elif method == 'mean':
            data[nan_mask] = np.nanmean(data)
        elif method == 'median':
            data[nan_mask] = np.nanmedian(data)
        
        return data
    
    def add_rolling_features(self, data, windows=(7, 14, 30)):
        """Add rolling statistics features.
        
        Args:
            data: 1D array of values
            windows: Tuple of window sizes
        
        Returns:
            2D array with original + rolling features
        """
        data = np.array(data, dtype=np.float64)
        features = [data]
        
        for w in windows:
            if len(data) >= w:
                # Rolling mean
                rolling_mean = np.convolve(data, np.ones(w) / w, mode='same')
                features.append(rolling_mean)
                
                # Rolling std
                rolling_std = np.array([
                    np.std(data[max(0, i - w//2):i + w//2 + 1])
                    for i in range(len(data))
                ])
                features.append(rolling_std)
                
                # Rolling min/max
                rolling_min = np.array([
                    np.min(data[max(0, i - w//2):i + w//2 + 1])
                    for i in range(len(data))
                ])
                rolling_max = np.array([
                    np.max(data[max(0, i - w//2):i + w//2 + 1])
                    for i in range(len(data))
                ])
                features.append(rolling_min)
                features.append(rolling_max)
        
        return np.column_stack(features)
    
    def add_lag_features(self, data, lags=(1, 7, 30)):
        """Add lag features.
        
        Args:
            data: 1D array
            lags: Tuple of lag values
        
        Returns:
            2D array with original + lag features
        """
        data = np.array(data, dtype=np.float64)
        features = [data]
        
        for lag in lags:
            lagged = np.roll(data, lag)
            lagged[:lag] = data[0]
            features.append(lagged)
        
        return np.column_stack(features)
    
    def add_rate_of_change(self, data):
        """Add rate of change features.
        
        Returns:
            2D array with original + first difference + percent change
        """
        data = np.array(data, dtype=np.float64)
        
        diff = np.diff(data, prepend=data[0])
        pct_change = diff / np.where(np.abs(data) < 1e-10, 1, data)
        
        return np.column_stack([data, diff, pct_change])
    
    def add_temporal_features(self, timestamps):
        """Extract temporal features from timestamps with cyclical encoding."""
        df = pd.DataFrame({'timestamp': pd.to_datetime(timestamps)})
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['day_of_month'] = df['timestamp'].dt.day
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['quarter'] = df['timestamp'].dt.quarter
        
        # Cyclical encoding
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        df['dom_sin'] = np.sin(2 * np.pi * df['day_of_month'] / 31)
        df['dom_cos'] = np.cos(2 * np.pi * df['day_of_month'] / 31)
        
        return df[['hour_sin', 'hour_cos', 'day_sin', 'day_cos', 
                    'month_sin', 'month_cos', 'dom_sin', 'dom_cos',
                    'is_weekend']].values
    
    def parse_csv(self, csv_text, required_columns=None):
        """Robustly parse CSV text with validation and error reporting.
        
        Args:
            csv_text: Raw CSV string
            required_columns: List of required column names
            
        Returns:
            dict with 'data' (DataFrame), 'errors' (list), 'warnings' (list)
        """
        errors = []
        warnings = []
        
        try:
            from io import StringIO
            df = pd.read_csv(StringIO(csv_text))
        except Exception as e:
            return {'data': None, 'errors': [f'CSV parse error: {str(e)}'], 'warnings': []}
        
        if len(df) == 0:
            errors.append('CSV file is empty')
            return {'data': None, 'errors': errors, 'warnings': warnings}
        
        if required_columns:
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                errors.append(f'Missing required columns: {missing}')
        
        # Check for NaN values
        nan_counts = df.isnull().sum()
        nan_cols = nan_counts[nan_counts > 0]
        if len(nan_cols) > 0:
            for col, count in nan_cols.items():
                warnings.append(f'Column "{col}" has {count} missing value(s)')
        
        # Check for negative values in consumption-like columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if 'consumption' in col.lower() or 'bill' in col.lower():
                neg_count = (df[col] < 0).sum()
                if neg_count > 0:
                    warnings.append(f'Column "{col}" has {neg_count} negative value(s)')
        
        self.data_stats = {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': df.columns.tolist(),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'nan_counts': {col: int(count) for col, count in nan_counts.items() if count > 0}
        }
        
        return {'data': df, 'errors': errors, 'warnings': warnings}
    
    def full_pipeline(self, data, clean_outliers=True, impute=True, 
                      add_features=True):
        """Run full preprocessing pipeline.
        
        Args:
            data: Raw 1D consumption data
            clean_outliers: Whether to detect and replace outliers
            impute: Whether to impute missing values
            add_features: Whether to add engineered features
        
        Returns:
            dict with 'processed' data and 'report' of processing steps
        """
        report = []
        processed = np.array(data, dtype=np.float64).copy()
        
        # Step 1: Impute missing values
        if impute:
            nan_count = np.sum(np.isnan(processed))
            if nan_count > 0:
                processed = self.impute_missing(processed)
                report.append(f'Imputed {nan_count} missing values')
        
        # Step 2: Detect and replace outliers
        if clean_outliers:
            outlier_result = self.detect_outliers(processed)
            if outlier_result['count'] > 0:
                processed = self.replace_outliers(processed)
                report.append(f'Replaced {outlier_result["count"]} outliers')
        
        # Step 3: Add features
        if add_features:
            # Rate of change
            roc = self.add_rate_of_change(processed)
            # Lag features
            lags = self.add_lag_features(processed, lags=(1, 7))
            # Rolling features (smaller windows for compatibility)
            rolling = self.add_rolling_features(processed, windows=(7,))
            
            # Combine
            feature_matrix = np.column_stack([
                roc,                # original + diff + pct_change
                lags[:, 1:],        # lag1, lag7 (skip original)
                rolling[:, 1:]      # rolling features (skip original)
            ])
            report.append(f'Added {feature_matrix.shape[1]} features')
        else:
            feature_matrix = processed.reshape(-1, 1)
        
        # Step 4: Normalize
        feature_matrix = self.normalize(feature_matrix)
        report.append('Normalized data')
        
        return {
            'processed': feature_matrix,
            'report': report,
            'shape': feature_matrix.shape
        }
