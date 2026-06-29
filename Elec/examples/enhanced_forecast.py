"""Enhanced forecasting example with hybrid model"""

import sys
sys.path.append('..')

import numpy as np
import matplotlib.pyplot as plt
from src.models.hybrid_model import HybridLSTMSVM
from src.data.preprocessor import EnergyDataPreprocessor
from src.forecasting.forecaster import EnergyForecaster
from src.evaluation.metrics import ForecastingMetrics


def generate_realistic_energy_data(n_samples=2000):
    """Generate realistic energy consumption pattern"""
    t = np.linspace(0, n_samples, n_samples)
    
    # Daily pattern (24-hour cycle)
    daily = 50 * np.sin(2 * np.pi * t / 24) + 100
    
    # Weekly pattern
    weekly = 20 * np.sin(2 * np.pi * t / (24 * 7))
    
    # Trend
    trend = 0.01 * t
    
    # Random noise
    noise = np.random.normal(0, 10, n_samples)
    
    # Combine patterns
    energy = daily + weekly + trend + noise
    return np.maximum(energy, 0)  # Ensure non-negative


def main():
    print("Enhanced Energy Forecasting Demo")
    print("="*50)
    
    # Generate data
    data = generate_realistic_energy_data(2000)
    
    # Preprocess
    preprocessor = EnergyDataPreprocessor(sequence_length=24)
    data_norm = preprocessor.normalize(data)
    X, y = preprocessor.create_sequences(data_norm)
    
    # Reshape for LSTM
    X = X.reshape(X.shape[0], X.shape[1], 1)
    
    # Split data
    train_size = int(0.7 * len(X))
    val_size = int(0.15 * len(X))
    
    X_train = X[:train_size]
    y_train = y[:train_size]
    X_val = X[train_size:train_size+val_size]
    y_val = y[train_size:train_size+val_size]
    X_test = X[train_size+val_size:]
    y_test = y[train_size+val_size:]
    
    print(f"Training samples: {len(X_train)}")
    print(f"Validation samples: {len(X_val)}")
    print(f"Test samples: {len(X_test)}")
    
    # Train hybrid model
    print("\nTraining Hybrid LSTM-SVM Model...")
    model = HybridLSTMSVM(sequence_length=24, features=1, lstm_weight=0.7)
    model.train(X_train, y_train, X_val, y_val, epochs=30)
    
    # Create forecaster
    forecaster = EnergyForecaster(model, preprocessor)
    
    # Make predictions
    print("\nMaking predictions...")
    predictions = forecaster.forecast_single_step(X_test)
    y_test_denorm = preprocessor.denormalize(y_test)
    
    # Evaluate
    metrics = ForecastingMetrics.calculate_all_metrics(y_test_denorm, predictions)
    ForecastingMetrics.print_metrics(metrics)
    
    # Multi-step forecast
    print("Performing 24-step ahead forecast...")
    initial_seq = data_norm[train_size+val_size:train_size+val_size+24]
    multi_step_pred = forecaster.forecast_multi_step(initial_seq, steps=24)
    
    print(f"Multi-step predictions (first 5): {multi_step_pred[:5]}")
    
    # Visualize results
    plt.figure(figsize=(15, 5))
    
    plt.subplot(1, 2, 1)
    plt.plot(y_test_denorm[:100], label='Actual', linewidth=2)
    plt.plot(predictions[:100], label='Predicted', linewidth=2, alpha=0.7)
    plt.title('Single-Step Forecast')
    plt.xlabel('Time Step')
    plt.ylabel('Energy Demand')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.subplot(1, 2, 2)
    actual_multi = preprocessor.denormalize(
        data_norm[train_size+val_size+24:train_size+val_size+48]
    )
    plt.plot(actual_multi, label='Actual', linewidth=2)
    plt.plot(multi_step_pred, label='24-Step Forecast', linewidth=2, alpha=0.7)
    plt.title('Multi-Step Forecast (24 hours ahead)')
    plt.xlabel('Time Step')
    plt.ylabel('Energy Demand')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('forecast_results.png', dpi=300, bbox_inches='tight')
    print("\nVisualization saved as 'forecast_results.png'")


if __name__ == "__main__":
    main()
