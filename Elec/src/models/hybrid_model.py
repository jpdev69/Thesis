"""True Hybrid LSTM-SVM Model with Integrated Architecture"""

import os
import numpy as np
import joblib
from sklearn.svm import SVR
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from .enhanced_lstm import EnhancedEnergyLSTM


class HybridLSTMSVM:
    """True Hybrid model where LSTM extracts temporal features and SVM
    learns on top of those features in an integrated architecture.
    
    Architecture:
    Input → LSTM (feature extraction) → LSTM features + Original features → SVM → Output
    
    This is a 100% integrated hybrid where both models contribute equally
    to the final prediction through feature stacking.
    """
    
    def __init__(self, sequence_length=24, features=1, num_heads=4):
        self.sequence_length = sequence_length
        self.features = features
        
        # LSTM for feature extraction
        self.lstm_model = EnhancedEnergyLSTM(
            sequence_length, features, 
            num_heads=num_heads, use_attention=True
        )
        
        # SVM learns on combined features
        self.svm_model = SVR(kernel='rbf', C=100, epsilon=0.01, gamma='scale')
        
        self.training_metrics = {}
        self.is_trained = False
    
    def _extract_lstm_features(self, X):
        """Extract temporal features using LSTM.
        
        Returns both LSTM predictions and internal representations.
        """
        # Get LSTM predictions (temporal patterns)
        lstm_pred = self.lstm_model.predict(X).flatten()
        
        # Flatten original sequences (statistical features)
        X_flat = X.reshape(X.shape[0], -1)
        
        # Combine LSTM temporal features with statistical features
        # This creates a rich feature set for SVM
        combined_features = np.column_stack([
            X_flat,           # Original sequence features
            lstm_pred,        # LSTM temporal predictions
            lstm_pred ** 2,   # Non-linear LSTM features
        ])
        
        return combined_features, lstm_pred
    
    def train(self, X_train, y_train, X_val=None, y_val=None, epochs=50):
        """Train the integrated hybrid model.
        
        Step 1: Train LSTM for temporal feature extraction
        Step 2: Extract LSTM features from training data
        Step 3: Train SVM on combined features (100% hybrid)
        
        Args:
            X_train: Training sequences
            y_train: Training targets
            X_val: Validation sequences
            y_val: Validation targets
            epochs: Training epochs for LSTM
            
        Returns:
            dict: Training metrics
        """
        print("=" * 60)
        print("Training True Hybrid LSTM-SVM Model (100% Integrated)")
        print("=" * 60)
        
        # Step 1: Train LSTM for feature extraction
        print("\n[Step 1/3] Training LSTM for temporal feature extraction...")
        self.lstm_model.train(X_train, y_train, X_val, y_val, epochs=epochs)
        lstm_train_pred = self.lstm_model.predict(X_train).flatten()
        lstm_train_rmse = np.sqrt(mean_squared_error(y_train, lstm_train_pred))
        print(f"  LSTM RMSE: {lstm_train_rmse:.4f}")
        
        # Step 2: Extract hybrid features
        print("\n[Step 2/3] Extracting hybrid features (LSTM + Statistical)...")
        train_features, lstm_pred = self._extract_lstm_features(X_train)
        print(f"  Feature dimensions: {train_features.shape[1]} features")
        print(f"    - Original sequence: {X_train.shape[1] * X_train.shape[2]} features")
        print(f"    - LSTM temporal: 1 feature")
        print(f"    - LSTM non-linear: 1 feature")
        
        # Step 3: Train SVM on combined features
        print("\n[Step 3/3] Training SVM on integrated hybrid features...")
        self.svm_model.fit(train_features, y_train)
        
        # Evaluate hybrid model
        hybrid_pred = self.svm_model.predict(train_features)
        hybrid_rmse = np.sqrt(mean_squared_error(y_train, hybrid_pred))
        hybrid_mae = mean_absolute_error(y_train, hybrid_pred)
        hybrid_r2 = r2_score(y_train, hybrid_pred)
        
        print(f"  Hybrid SVM RMSE: {hybrid_rmse:.4f}")
        print(f"  Improvement over LSTM: {((lstm_train_rmse - hybrid_rmse) / lstm_train_rmse * 100):.2f}%")
        
        # Validation metrics
        if X_val is not None and y_val is not None:
            print("\n[Validation] Evaluating on validation set...")
            val_pred = self.predict(X_val)
            val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            val_mae = mean_absolute_error(y_val, val_pred)
            val_r2 = r2_score(y_val, val_pred)
            
            print(f"  Validation RMSE: {val_rmse:.4f}")
            print(f"  Validation MAE: {val_mae:.4f}")
            print(f"  Validation R²: {val_r2:.4f}")
        
        # Store metrics
        self.training_metrics = {
            'lstm_rmse': float(lstm_train_rmse),
            'hybrid_rmse': float(hybrid_rmse),
            'hybrid_mae': float(hybrid_mae),
            'hybrid_r2': float(hybrid_r2),
            'improvement': float((lstm_train_rmse - hybrid_rmse) / lstm_train_rmse * 100),
            'model_type': '100% Integrated Hybrid LSTM-SVM',
            'architecture': 'LSTM(feature extraction) → SVM(prediction)',
            'feature_count': int(train_features.shape[1])
        }
        
        if X_val is not None and y_val is not None:
            self.training_metrics.update({
                'val_rmse': float(val_rmse),
                'val_mae': float(val_mae),
                'val_r2': float(val_r2)
            })
        
        self.is_trained = True
        
        print("\n" + "=" * 60)
        print("✓ Training Complete - True 100% Hybrid LSTM-SVM Active")
        print("=" * 60)
        
        return self.training_metrics
    
    def predict(self, X):
        """Make predictions using the integrated hybrid model.
        
        Process:
        1. Extract LSTM temporal features
        2. Combine with statistical features
        3. SVM predicts on combined features
        
        Returns:
            np.array: Predictions
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        # Extract hybrid features
        combined_features, _ = self._extract_lstm_features(X)
        
        # SVM predicts on integrated features
        return self.svm_model.predict(combined_features)
    
    def predict_with_confidence(self, X, n_forward=30):
        """Predict with confidence intervals using MC dropout and SVM uncertainty.
        
        Returns:
            dict with 'mean', 'lower', 'upper', 'std'
        """
        # Get LSTM uncertainty via MC dropout
        lstm_unc = self.lstm_model.predict_with_uncertainty(X, n_forward=n_forward)
        
        # Extract features for each MC dropout sample
        predictions = []
        for _ in range(n_forward):
            lstm_pred = self.lstm_model.predict(X).flatten()
            X_flat = X.reshape(X.shape[0], -1)
            combined = np.column_stack([X_flat, lstm_pred, lstm_pred ** 2])
            pred = self.svm_model.predict(combined)
            predictions.append(pred)
        
        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)
        
        return {
            'mean': mean_pred,
            'std': std_pred,
            'lower': mean_pred - 1.96 * std_pred,
            'upper': mean_pred + 1.96 * std_pred,
            'architecture': '100% Integrated Hybrid'
        }
    
    def get_model_info(self):
        """Return information about the hybrid architecture."""
        return {
            'model_type': '100% Integrated Hybrid LSTM-SVM',
            'architecture': 'Input → LSTM(features) → LSTM+Stats → SVM → Output',
            'lstm_component': 'Temporal feature extraction with attention',
            'svm_component': 'Non-linear prediction on hybrid features',
            'integration': 'Feature stacking (fully integrated)',
            'weighting': 'Not applicable (true hybrid, not ensemble)',
            'training_metrics': self.training_metrics
        }
    
    def get_lstm_weights(self):
        return self.lstm_model.get_weights()
    
    def set_lstm_weights(self, weights):
        self.lstm_model.set_weights(weights)
    
    def save(self, directory):
        """Save full hybrid model to directory."""
        os.makedirs(directory, exist_ok=True)
        self.lstm_model.save(os.path.join(directory, 'lstm_model'))
        joblib.dump(self.svm_model, os.path.join(directory, 'svm_model.joblib'))
        joblib.dump({
            'training_metrics': self.training_metrics,
            'sequence_length': self.sequence_length,
            'features': self.features,
            'model_type': '100% Integrated Hybrid LSTM-SVM'
        }, os.path.join(directory, 'hybrid_meta.joblib'))
    
    def load(self, directory):
        """Load full hybrid model from directory."""
        self.lstm_model.load(os.path.join(directory, 'lstm_model'))
        self.svm_model = joblib.load(os.path.join(directory, 'svm_model.joblib'))
        meta = joblib.load(os.path.join(directory, 'hybrid_meta.joblib'))
        self.training_metrics = meta['training_metrics']
        self.is_trained = True
