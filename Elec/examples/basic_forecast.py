"""Basic energy forecasting example"""

import sys
sys.path.append('..')

import numpy as np
from src.models.lstm_model import EnergyLSTM
from src.data.preprocessor import EnergyDataPreprocessor


def main():
    # Generate sample data
    np.random.seed(42)
    data = np.sin(np.linspace(0, 100, 1000)) + np.random.normal(0, 0.1, 1000)
    
    # Preprocess
    preprocessor = EnergyDataPreprocessor(sequence_length=24)
    data_norm = preprocessor.normalize(data)
    X, y = preprocessor.create_sequences(data_norm)
    
    # Split data
    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Reshape for LSTM
    X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
    X_test = X_test.reshape(X_test.shape[0], X_test.shape[1], 1)
    
    # Train model
    model = EnergyLSTM(sequence_length=24, features=1)
    model.train(X_train, y_train, epochs=10)
    
    # Predict
    predictions = model.predict(X_test)
    print(f"Predictions shape: {predictions.shape}")
    print(f"Sample predictions: {predictions[:5].flatten()}")


if __name__ == "__main__":
    main()
