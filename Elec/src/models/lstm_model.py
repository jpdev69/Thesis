"""Enhanced LSTM model for energy forecasting with scheduling, multi-feature support, and persistence"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks


class EnergyLSTM:
    """LSTM model with cosine annealing, multi-feature support, 
    model checkpointing, and comprehensive training history."""
    
    def __init__(self, sequence_length=24, features=1, units=(128, 64), 
                 dropout_rate=0.3, learning_rate=0.001):
        self.sequence_length = sequence_length
        self.features = features
        self.units = units
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.model = self._build_model()
        self.history = None
        self.is_trained = False
    
    def _build_model(self):
        """Build enhanced LSTM with configurable layers and regularization."""
        model = keras.Sequential()
        
        # Input LSTM layers
        for i, unit_count in enumerate(self.units):
            return_seq = (i < len(self.units) - 1)
            if i == 0:
                model.add(layers.LSTM(
                    unit_count, return_sequences=return_seq,
                    input_shape=(self.sequence_length, self.features),
                    kernel_regularizer=keras.regularizers.l2(1e-4)
                ))
            else:
                model.add(layers.LSTM(
                    unit_count, return_sequences=return_seq,
                    kernel_regularizer=keras.regularizers.l2(1e-4)
                ))
            model.add(layers.BatchNormalization())
            model.add(layers.Dropout(self.dropout_rate))
        
        # Dense output layers
        model.add(layers.Dense(32, activation='relu'))
        model.add(layers.Dropout(self.dropout_rate * 0.5))
        model.add(layers.Dense(1))
        
        # Cosine annealing schedule
        lr_schedule = keras.optimizers.schedules.CosineDecay(
            initial_learning_rate=self.learning_rate,
            decay_steps=1000,
            alpha=1e-6
        )
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=lr_schedule),
            loss='huber',  # More robust than MSE
            metrics=['mae', 'mape']
        )
        return model
    
    def _get_callbacks(self, checkpoint_path=None):
        """Build training callbacks including early stopping and LR scheduling."""
        cb_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=15,
                restore_best_weights=True,
                min_delta=1e-5
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=7,
                min_lr=1e-7,
                verbose=1
            ),
            callbacks.TerminateOnNaN()
        ]
        
        if checkpoint_path:
            os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
            cb_list.append(callbacks.ModelCheckpoint(
                filepath=checkpoint_path,
                monitor='val_loss',
                save_best_only=True,
                verbose=0
            ))
        
        return cb_list
    
    def train(self, X_train, y_train, epochs=100, batch_size=32, 
              validation_split=0.2, checkpoint_path=None):
        """Train with comprehensive callbacks and history tracking.
        
        Args:
            X_train: Training sequences
            y_train: Training targets  
            epochs: Max training epochs
            batch_size: Batch size
            validation_split: Fraction for validation
            checkpoint_path: Optional path to save best model checkpoint
            
        Returns:
            Training history object with epoch-level metrics
        """
        cb_list = self._get_callbacks(checkpoint_path)
        
        self.history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=cb_list,
            verbose=1
        )
        
        self.is_trained = True
        return self.history
    
    def predict(self, X):
        """Standard prediction."""
        return self.model.predict(X, verbose=0)
    
    def predict_with_uncertainty(self, X, n_forward=50):
        """Monte Carlo Dropout prediction for uncertainty estimation.
        
        Runs multiple forward passes with dropout enabled to estimate
        prediction uncertainty.
        
        Returns:
            dict with 'mean', 'std', 'lower', 'upper' arrays
        """
        predictions = []
        for _ in range(n_forward):
            pred = self.model(X, training=True)  # Enable dropout
            predictions.append(pred.numpy())
        
        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)
        std_pred = np.std(predictions, axis=0)
        
        return {
            'mean': mean_pred.flatten(),
            'std': std_pred.flatten(),
            'lower': (mean_pred - 1.96 * std_pred).flatten(),
            'upper': (mean_pred + 1.96 * std_pred).flatten()
        }
    
    def get_training_summary(self):
        """Return summary of training metrics."""
        if self.history is None:
            return {}
        
        h = self.history.history
        return {
            'final_loss': float(h['loss'][-1]),
            'final_val_loss': float(h.get('val_loss', [0])[-1]),
            'final_mae': float(h['mae'][-1]),
            'final_val_mae': float(h.get('val_mae', [0])[-1]),
            'best_val_loss': float(min(h.get('val_loss', [0]))),
            'epochs_trained': len(h['loss']),
            'converged': len(h['loss']) < 100  # Stopped early
        }
    
    def get_weights(self):
        return self.model.get_weights()
    
    def set_weights(self, weights):
        self.model.set_weights(weights)
    
    def save(self, filepath):
        """Save full model to disk."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        self.model.save(filepath)
    
    def load(self, filepath):
        """Load model from disk."""
        self.model = keras.models.load_model(filepath)
        self.is_trained = True
