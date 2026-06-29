"""Federated learning example with multiple campus buildings"""

import sys
sys.path.append('..')

import numpy as np
from src.models.enhanced_lstm import EnhancedEnergyLSTM
from src.data.preprocessor import EnergyDataPreprocessor
from src.federated.aggregator import FederatedAggregator
from src.evaluation.metrics import ForecastingMetrics


def simulate_building_data(building_id, n_samples=1000):
    """Simulate energy data for different buildings"""
    t = np.linspace(0, n_samples, n_samples)
    
    # Each building has slightly different patterns
    base_load = 80 + building_id * 20
    daily = (40 + building_id * 5) * np.sin(2 * np.pi * t / 24)
    noise = np.random.normal(0, 8, n_samples)
    
    return np.maximum(base_load + daily + noise, 0)


def main():
    print("Federated Learning for Campus Energy Forecasting")
    print("="*60)
    
    # Simulate 3 campus buildings
    num_buildings = 3
    sequence_length = 24
    
    # Initialize global model
    global_model = EnhancedEnergyLSTM(sequence_length=sequence_length, features=1)
    aggregator = FederatedAggregator(aggregation_method='fedavg')
    
    # Federated training rounds
    num_rounds = 5
    
    for round_num in range(num_rounds):
        print(f"\n{'='*60}")
        print(f"Federated Round {round_num + 1}/{num_rounds}")
        print(f"{'='*60}")
        
        client_weights = []
        client_samples = []
        
        # Train on each building (client)
        for building_id in range(num_buildings):
            print(f"\nTraining on Building {building_id + 1}...")
            
            # Generate building-specific data
            data = simulate_building_data(building_id, n_samples=1000)
            
            # Preprocess
            preprocessor = EnergyDataPreprocessor(sequence_length=sequence_length)
            data_norm = preprocessor.normalize(data)
            X, y = preprocessor.create_sequences(data_norm)
            X = X.reshape(X.shape[0], X.shape[1], 1)
            
            # Split
            train_size = int(0.8 * len(X))
            X_train, y_train = X[:train_size], y[:train_size]
            X_test, y_test = X[train_size:], y[train_size:]
            
            # Create local model with global weights
            local_model = EnhancedEnergyLSTM(sequence_length=sequence_length, features=1)
            if round_num > 0:
                local_model.set_weights(global_weights)
            
            # Local training
            local_model.train(X_train, y_train, epochs=5, batch_size=32)
            
            # Evaluate local model
            predictions = local_model.predict(X_test)
            y_test_denorm = preprocessor.denormalize(y_test)
            pred_denorm = preprocessor.denormalize(predictions.flatten())
            
            metrics = ForecastingMetrics.calculate_all_metrics(y_test_denorm, pred_denorm)
            print(f"Building {building_id + 1} - RMSE: {metrics['RMSE']:.4f}, MAE: {metrics['MAE']:.4f}")
            
            # Collect weights
            client_weights.append(local_model.get_weights())
            client_samples.append(len(X_train))
        
        # Aggregate weights
        print(f"\nAggregating weights from {num_buildings} buildings...")
        global_weights = aggregator.aggregate_weights(client_weights, client_samples)
        global_model.set_weights(global_weights)
        
        print(f"Round {round_num + 1} completed!")
    
    print("\n" + "="*60)
    print("Federated training completed!")
    print("="*60)
    print("\nThe global model now contains knowledge from all campus buildings")
    print("while preserving privacy of individual building data.")


if __name__ == "__main__":
    main()
