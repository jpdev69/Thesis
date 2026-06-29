"""
Campus Electricity Bill Forecasting
Uses REAL monthly bill data (in Philippine Peso)
"""

import sys
sys.path.append('..')

import numpy as np
import pandas as pd
from src.models.hybrid_model import HybridLSTMSVM
from src.data.preprocessor import EnergyDataPreprocessor
from src.evaluation.metrics import ForecastingMetrics


def load_campus_bills(csv_file=None):
    """
    Load real campus electricity bills
    
    If csv_file is provided, loads from CSV with columns: [Month, Bill]
    Otherwise, returns example format for you to fill in
    """
    if csv_file:
        df = pd.read_csv(csv_file)
        return df['Bill'].values
    else:
        # REPLACE THIS WITH YOUR ACTUAL CAMPUS BILLS
        # Format: Monthly bills in Philippine Peso
        print("⚠️  Using example data. Replace with your actual bills!")
        print("   Edit this function and add your real monthly bills.\n")
        
        return np.array([
            # 2022 (Example - REPLACE WITH YOUR DATA)
            38000, 40000, 42000, 45000, 48000, 46000,  # Jan-Jun
            44000, 42000, 40000, 41000, 43000, 45000,  # Jul-Dec
            
            # 2023 (Example - REPLACE WITH YOUR DATA)
            42000, 45000, 48000, 52000, 56000, 54000,  # Jan-Jun
            51000, 49000, 47000, 48000, 50000, 52000,  # Jul-Dec
            
            # 2024 (Example - REPLACE WITH YOUR DATA)
            45000, 48000, 52000, 55000, 58000, 54000,  # Jan-Jun
            50000, 48000, 46000, 49000, 51000, 53000   # Jul-Dec
        ])


def main():
    print("="*60)
    print("CAMPUS ELECTRICITY BILL FORECASTING")
    print("="*60)
    
    # Load YOUR real campus bills
    campus_bills = load_campus_bills()
    
    print(f"\n📊 Data Summary:")
    print(f"   Total months: {len(campus_bills)}")
    print(f"   Date range: {len(campus_bills)} months")
    print(f"   Average bill: ₱{np.mean(campus_bills):,.0f}")
    print(f"   Minimum bill: ₱{np.min(campus_bills):,.0f}")
    print(f"   Maximum bill: ₱{np.max(campus_bills):,.0f}")
    print(f"   Latest bill: ₱{campus_bills[-1]:,.0f}")
    
    # Check if we have enough data
    if len(campus_bills) < 24:
        print("\n⚠️  Warning: Need at least 24 months of data for best results")
        print(f"   You have: {len(campus_bills)} months")
        print("   Continuing anyway, but accuracy may be lower...\n")
    
    # Preprocess data
    print("\n🔧 Preprocessing data...")
    preprocessor = EnergyDataPreprocessor(sequence_length=12)  # Use 12 months
    data_norm = preprocessor.normalize(campus_bills)
    X, y = preprocessor.create_sequences(data_norm)
    
    # Reshape for LSTM
    X = X.reshape(X.shape[0], X.shape[1], 1)
    
    print(f"   Created {len(X)} training sequences")
    
    # Split data (80% train, 20% test)
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"   Training samples: {len(X_train)}")
    print(f"   Testing samples: {len(X_test)}")
    
    # Train model
    print("\n🤖 Training Hybrid LSTM-SVM Model...")
    print("   This may take a few minutes...")
    
    model = HybridLSTMSVM(
        sequence_length=12,
        features=1,
        lstm_weight=0.7  # 70% LSTM, 30% SVM
    )
    
    model.train(X_train, y_train, epochs=50)
    
    # Make predictions on test set
    print("\n📈 Making predictions...")
    predictions_norm = model.predict(X_test)
    predictions = preprocessor.denormalize(predictions_norm)
    y_test_actual = preprocessor.denormalize(y_test)
    
    # Calculate metrics
    metrics = ForecastingMetrics.calculate_all_metrics(y_test_actual, predictions)
    
    print("\n✅ Model Performance:")
    print(f"   RMSE: ₱{metrics['RMSE']:,.0f}")
    print(f"   MAE: ₱{metrics['MAE']:,.0f}")
    print(f"   MAPE: {metrics['MAPE']:.2f}%")
    print(f"   R² Score: {metrics['R2']:.4f}")
    
    # Show sample predictions vs actual
    print("\n📊 Sample Predictions vs Actual:")
    print("   " + "-"*50)
    print(f"   {'Month':<10} {'Actual':<15} {'Predicted':<15} {'Error':<10}")
    print("   " + "-"*50)
    
    for i in range(min(5, len(y_test_actual))):
        actual = y_test_actual[i]
        pred = predictions[i]
        error = abs(actual - pred)
        print(f"   Month {i+1:<4} ₱{actual:>12,.0f}  ₱{pred:>12,.0f}  ₱{error:>8,.0f}")
    
    # Predict next month
    print("\n🔮 Forecasting Next Month's Bill:")
    print("   " + "-"*50)
    
    last_12_months = campus_bills[-12:]
    last_12_norm = preprocessor.normalize(last_12_months)
    last_12_reshaped = last_12_norm.reshape(1, 12, 1)
    
    next_month_norm = model.predict(last_12_reshaped)
    next_month_bill = preprocessor.denormalize(next_month_norm)[0]
    
    print(f"   Last 12 months average: ₱{np.mean(last_12_months):,.0f}")
    print(f"   Last month's bill: ₱{campus_bills[-1]:,.0f}")
    print(f"   📍 PREDICTED NEXT MONTH: ₱{next_month_bill:,.0f}")
    
    # Calculate confidence interval (±2 standard deviations)
    std_error = metrics['RMSE']
    lower_bound = next_month_bill - (2 * std_error)
    upper_bound = next_month_bill + (2 * std_error)
    
    print(f"\n   95% Confidence Interval:")
    print(f"   Lower bound: ₱{lower_bound:,.0f}")
    print(f"   Upper bound: ₱{upper_bound:,.0f}")
    
    # Predict next 3 months
    print("\n🔮 Forecasting Next 3 Months:")
    print("   " + "-"*50)
    
    current_sequence = last_12_norm.copy()
    predictions_3_months = []
    
    for month in range(1, 4):
        # Predict next month
        next_pred_norm = model.predict(current_sequence.reshape(1, 12, 1))[0]
        next_pred = preprocessor.denormalize(np.array([next_pred_norm]))[0]
        predictions_3_months.append(next_pred)
        
        # Update sequence (remove oldest, add newest)
        current_sequence = np.append(current_sequence[1:], next_pred_norm)
        
        print(f"   Month +{month}: ₱{next_pred:,.0f}")
    
    total_3_months = sum(predictions_3_months)
    print(f"\n   Total for next 3 months: ₱{total_3_months:,.0f}")
    print(f"   Average per month: ₱{total_3_months/3:,.0f}")
    
    # Budget recommendation
    print("\n💰 Budget Recommendation:")
    print("   " + "-"*50)
    buffer = 0.10  # 10% buffer
    recommended_budget = total_3_months * (1 + buffer)
    print(f"   Predicted 3-month cost: ₱{total_3_months:,.0f}")
    print(f"   + {buffer*100:.0f}% contingency buffer: ₱{total_3_months * buffer:,.0f}")
    print(f"   📍 RECOMMENDED BUDGET: ₱{recommended_budget:,.0f}")
    
    print("\n" + "="*60)
    print("✅ Forecasting Complete!")
    print("="*60)


if __name__ == "__main__":
    main()
