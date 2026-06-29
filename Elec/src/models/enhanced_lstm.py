"""Enhanced LSTM with Multi-Head Attention, Residual Connections, and Uncertainty Estimation"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


class MultiHeadAttentionLayer(layers.Layer):
    """Multi-head attention mechanism for time series."""
    
    def __init__(self, d_model, num_heads, **kwargs):
        super().__init__(**kwargs)
        self.num_heads = num_heads
        self.d_model = d_model
        assert d_model % num_heads == 0
        
        self.depth = d_model // num_heads
        self.wq = layers.Dense(d_model)
        self.wk = layers.Dense(d_model)
        self.wv = layers.Dense(d_model)
        self.dense = layers.Dense(d_model)
    
    def split_heads(self, x, batch_size):
        x = tf.reshape(x, (batch_size, -1, self.num_heads, self.depth))
        return tf.transpose(x, perm=[0, 2, 1, 3])
    
    def call(self, v, k, q):
        batch_size = tf.shape(q)[0]
        
        q = self.split_heads(self.wq(q), batch_size)
        k = self.split_heads(self.wk(k), batch_size)
        v = self.split_heads(self.wv(v), batch_size)
        
        # Scaled dot-product attention
        matmul_qk = tf.matmul(q, k, transpose_b=True)
        dk = tf.cast(tf.shape(k)[-1], tf.float32)
        scaled_attention_logits = matmul_qk / tf.math.sqrt(dk)
        attention_weights = tf.nn.softmax(scaled_attention_logits, axis=-1)
        
        output = tf.matmul(attention_weights, v)
        output = tf.transpose(output, perm=[0, 2, 1, 3])
        output = tf.reshape(output, (batch_size, -1, self.d_model))
        
        return self.dense(output), attention_weights
    
    def get_config(self):
        config = super().get_config()
        config.update({'d_model': self.d_model, 'num_heads': self.num_heads})
        return config


class ResidualBlock(layers.Layer):
    """Residual connection with layer normalization."""
    
    def __init__(self, d_model, **kwargs):
        super().__init__(**kwargs)
        self.layer_norm = layers.LayerNormalization(epsilon=1e-6)
        self.d_model = d_model
    
    def call(self, x, sublayer_output):
        # Project x if dimensions don't match
        if x.shape[-1] != sublayer_output.shape[-1]:
            x = layers.Dense(sublayer_output.shape[-1])(x)
        return self.layer_norm(x + sublayer_output)
    
    def get_config(self):
        config = super().get_config()
        config.update({'d_model': self.d_model})
        return config


class EnhancedEnergyLSTM:
    """Enhanced LSTM with multi-head attention, residual connections,
    layer normalization, and Monte Carlo dropout for uncertainty."""
    
    def __init__(self, sequence_length=24, features=1, use_attention=True,
                 num_heads=4, num_lstm_layers=2, d_model=64, 
                 dropout_rate=0.3, use_residual=True):
        self.sequence_length = sequence_length
        self.features = features
        self.use_attention = use_attention
        self.num_heads = num_heads
        self.num_lstm_layers = num_lstm_layers
        self.d_model = d_model
        self.dropout_rate = dropout_rate
        self.use_residual = use_residual
        self.model = self._build_model()
        self.attention_weights = None
        self.is_trained = False
    
    def _build_model(self):
        inputs = keras.Input(shape=(self.sequence_length, self.features))
        
        # Project input to d_model dimensions
        x = layers.Dense(self.d_model)(inputs)
        
        # Stacked LSTM layers with residual connections
        lstm_units = [self.d_model * 2, self.d_model]
        for i in range(self.num_lstm_layers):
            units = lstm_units[i] if i < len(lstm_units) else self.d_model
            lstm_out = layers.LSTM(
                units, return_sequences=True,
                kernel_regularizer=keras.regularizers.l2(1e-4)
            )(x)
            lstm_out = layers.LayerNormalization(epsilon=1e-6)(lstm_out)
            lstm_out = layers.Dropout(self.dropout_rate)(lstm_out)
            
            # Residual connection (dimension-matched)
            if self.use_residual:
                if x.shape[-1] != lstm_out.shape[-1]:
                    x = layers.Dense(lstm_out.shape[-1])(x)
                x = layers.Add()([x, lstm_out])
                x = layers.LayerNormalization(epsilon=1e-6)(x)
            else:
                x = lstm_out
        
        if self.use_attention:
            # Multi-head attention
            attn_output, _ = MultiHeadAttentionLayer(
                d_model=x.shape[-1], num_heads=self.num_heads
            )(x, x, x)
            attn_output = layers.Dropout(self.dropout_rate)(attn_output)
            
            if self.use_residual:
                x = layers.Add()([x, attn_output])
                x = layers.LayerNormalization(epsilon=1e-6)(x)
            else:
                x = attn_output
            
            # Global average pooling over time
            x = layers.GlobalAveragePooling1D()(x)
        else:
            # Take last time step
            x = layers.Lambda(lambda t: t[:, -1, :])(x)
        
        # Feed-forward output network
        x = layers.Dense(64, activation='gelu')(x)
        x = layers.Dropout(self.dropout_rate * 0.5)(x)
        x = layers.Dense(32, activation='gelu')(x)
        x = layers.Dropout(self.dropout_rate * 0.3)(x)
        outputs = layers.Dense(1)(x)
        
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
    
    def train(self, X_train, y_train, X_val=None, y_val=None, 
              epochs=100, batch_size=32):
        """Train with comprehensive callbacks."""
        cb_list = [
            keras.callbacks.EarlyStopping(
                patience=15, restore_best_weights=True, monitor='val_loss'
            ),
            keras.callbacks.ReduceLROnPlateau(
                factor=0.5, patience=7, min_lr=1e-7
            ),
            keras.callbacks.TerminateOnNaN()
        ]
        
        validation_data = (X_val, y_val) if X_val is not None else None
        validation_split = 0.2 if validation_data is None else 0.0
        
        history = self.model.fit(
            X_train, y_train,
            validation_data=validation_data,
            validation_split=validation_split,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=cb_list,
            verbose=1
        )
        
        self.is_trained = True
        return history
    
    def predict(self, X):
        """Standard prediction."""
        return self.model.predict(X, verbose=0)
    
    def predict_with_uncertainty(self, X, n_forward=50):
        """Monte Carlo Dropout for prediction intervals.
        
        Returns:
            dict with 'mean', 'std', 'lower', 'upper', 'p10', 'p50', 'p90'
        """
        predictions = []
        for _ in range(n_forward):
            pred = self.model(X, training=True)  # Dropout enabled
            predictions.append(pred.numpy())
        
        preds = np.array(predictions).squeeze()
        
        return {
            'mean': np.mean(preds, axis=0),
            'std': np.std(preds, axis=0),
            'lower': np.percentile(preds, 2.5, axis=0),
            'upper': np.percentile(preds, 97.5, axis=0),
            'p10': np.percentile(preds, 10, axis=0),
            'p50': np.percentile(preds, 50, axis=0),
            'p90': np.percentile(preds, 90, axis=0)
        }
    
    def get_weights(self):
        return self.model.get_weights()
    
    def set_weights(self, weights):
        self.model.set_weights(weights)
    
    def save(self, filepath):
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        self.model.save(filepath)
    
    def load(self, filepath):
        self.model = keras.models.load_model(
            filepath,
            custom_objects={
                'MultiHeadAttentionLayer': MultiHeadAttentionLayer,
                'ResidualBlock': ResidualBlock
            }
        )
        self.is_trained = True
