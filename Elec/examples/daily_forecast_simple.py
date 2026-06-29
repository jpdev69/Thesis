"""
Daily Campus Electricity Forecasting - Simplified Version
Works without TensorFlow - uses statistical methods for demonstration
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class SimpleDailyPredictor:
    """Simplified daily predictor using Ridge regression"""
    
    def __init__(self, sequence_length=7):
        self.sequence_length = sequence_length
        self.model = Ridge(alpha=1.0)
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def prepare_features(self, consumption, temperature, humidity, rainfall, 
                        has_classes, day_of_week, is_weekend):
        """Prepare feature matrix"""
        features = np.column_stack([
            consumption,
            temperature,
            humidity,
            rainfall,
            has_classes,
            is_weekend,
            np.sin(2 * np.pi * day_of_week / 7),
            np.cos(2 * np.pi * day_of_week / 7)
        ])
        return features
    
    def create_sequences(self, features, targets):
        """Create sequences for prediction"""
        X, y = [], []
        for i in range(len(features) - self.sequence_length):
            X.append(features[i:i + self.sequence_length].flatten())
            y.append(targets[i + self.sequence_length])
        return np.array(X), np.array(y)
    
    def train(self, consumption, temperature, humidity, rainfall,
              has_classes, day_of_week, is_weekend):
        """Train the model"""
        print("Preparing features...")
        
        features = self.prepare_features(
            consumption, temperature, humidity, rainfall,
            has_classes, day_of_week, is_weekend
        )
        
        # Normalize features
        features_norm = self.scaler.fit_transform(features)
        
        # Create sequences
        X, y = self.create_sequences(features_norm, consumption)
        
        print(f"Created {len(X)} training sequences")
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Train model
        print("\nTraining model...")
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate
        print("\nEvaluating model...")
        val_pred = self.model.predict(X_val)
        
        rmse = np.sqrt(np.mean((y_val - val_pred) ** 2))
        mae = np.mean(np.abs(y_val - val_pred))
        mape = np.mean(np.abs((y_val - val_pred) / y_val)) * 100
        
        mean = np.mean(y_val)
        ss_res = np.sum((y_val - val_pred) ** 2)
        ss_tot = np.sum((y_val - mean) ** 2)
        r2 = 1 - (ss_res / ss_tot)
        
        print(f"\nValidation Metrics:")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  MAE: {mae:.2f}")
        print(f"  MAPE: {mape:.2f}%")
        print(f"  R² Score: {r2:.4f}")
        
        return {'RMSE': rmse, 'MAE': mae, 'MAPE': mape, 'R2': r2}
    
    def predict_next_n_days(self, past_data, future_weather, future_schedule, n_days=7):
        """Predict next N days"""
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        predictions = []
        
        # Start with past data
        current_consumption = past_data['consumption'].copy()
        current_temperature = past_data['temperature'].copy()
        current_humidity = past_data['humidity'].copy()
        current_rainfall = past_data['rainfall'].copy()
        current_has_classes = past_data['has_classes'].copy()
        current_day_of_week = past_data['day_of_week'].copy()
        current_is_weekend = past_data['is_weekend'].copy()
        
        for day in range(n_days):
            # Prepare features
            features = self.prepare_features(
                current_consumption[-self.sequence_length:],
                current_temperature[-self.sequence_length:],
                current_humidity[-self.sequence_length:],
                current_rainfall[-self.sequence_length:],
                current_has_classes[-self.sequence_length:],
                current_day_of_week[-self.sequence_length:],
                current_is_weekend[-self.sequence_length:]
            )
            
            # Normalize
            features_norm = self.scaler.transform(features)
            
            # Predict
            X = features_norm.flatten().reshape(1, -1)
            pred = self.model.predict(X)[0]
            predictions.append(pred)
            
            # Update current data
            current_consumption = np.append(current_consumption, pred)
            current_temperature = np.append(current_temperature, future_weather['temperature'][day])
            current_humidity = np.append(current_humidity, future_weather['humidity'][day])
            current_rainfall = np.append(current_rainfall, future_weather['rainfall'][day])
            current_has_classes = np.append(current_has_classes, future_schedule['has_classes'][day])
            current_day_of_week = np.append(current_day_of_week, future_schedule['day_of_week'][day])
            current_is_weekend = np.append(current_is_weekend, future_schedule['is_weekend'][day])
        
        return np.array(predictions)


def load_historical_data():
    """Generate sample historical data"""
    print("⚠️  Using example data. Replace with your actual daily records!\n")
    
    # Generate 90 days of example data
    dates = pd.date_range(start='2024-09-01', periods=90, freq='D')
    
    data = {
        'Date': dates,
        'Consumption': [],
        'Temperature': [],
        'Humidity': [],
        'Rainfall': [],
        'HasClasses': []
    }
    
    for date in dates:
        day_of_week = date.dayofweek
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Base consumption
        base = 1500  # kWh per day
        
        # Temperature effect
        temp = 28 + np.random.normal(0, 3)
        temp_effect = (temp - 25) * 50
        
        # Humidity effect
        humidity = 70 + np.random.normal(0, 10)
        
        # Rainfall effect
        rainfall = max(0, np.random.exponential(5))
        rain_effect = -rainfall * 10
        
        # Class schedule effect
        has_classes = 0 if is_weekend else 1
        class_effect = -300 if has_classes == 0 else 0
        
        # Weekend effect
        weekend_effect = -200 if is_weekend else 0
        
        # Calculate consumption
        consumption = base + temp_effect + rain_effect + class_effect + weekend_effect
        consumption = max(800, consumption + np.random.normal(0, 50))
        
        data['Consumption'].append(consumption)
        data['Temperature'].append(temp)
        data['Humidity'].append(humidity)
        data['Rainfall'].append(rainfall)
        data['HasClasses'].append(has_classes)
    
    df = pd.DataFrame(data)
    df['DayOfWeek'] = df['Date'].dt.dayofweek
    df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
    
    return df


def get_weather_forecast(days=7):
    """Get weather forecast"""
    print("⚠️  Using example weather forecast. Integrate with real weather API!\n")
    
    forecast = {
        'temperature': 28 + np.random.normal(0, 2, days),
        'humidity': 70 + np.random.normal(0, 5, days),
        'rainfall': np.maximum(0, np.random.exponential(3, days))
    }
    
    return forecast


def get_campus_schedule(start_date, days=7):
    """Get campus schedule"""
    schedule = {
        'has_classes': [],
        'day_of_week': [],
        'is_weekend': []
    }
    
    current_date = start_date
    for _ in range(days):
        day_of_week = current_date.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        has_classes = 0 if is_weekend else 1
        
        schedule['has_classes'].append(has_classes)
        schedule['day_of_week'].append(day_of_week)
        schedule['is_weekend'].append(is_weekend)
        
        current_date += timedelta(days=1)
    
    return {k: np.array(v) for k, v in schedule.items()}


def main():
    print("="*70)
    print("DAILY CAMPUS ELECTRICITY FORECASTING (Simplified Version)")
    print("Weather-Aware & Schedule-Aware Predictions")
    print("="*70)
    
    # Load historical data
    print("\n📊 Loading historical data...")
    df = load_historical_data()
    
    print(f"   Data range: {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"   Total days: {len(df)}")
    print(f"   Average consumption: {df['Consumption'].mean():.0f} kWh/day")
    
    # Show consumption patterns
    print("\n📈 Consumption Patterns:")
    class_days = df[df['HasClasses'] == 1]['Consumption'].mean()
    no_class_days = df[df['HasClasses'] == 0]['Consumption'].mean()
    
    print(f"   Class days average: {class_days:.0f} kWh/day")
    print(f"   No-class days average: {no_class_days:.0f} kWh/day")
    print(f"   Difference: {class_days - no_class_days:.0f} kWh/day ({((class_days-no_class_days)/no_class_days*100):.1f}%)")
    
    # Prepare training data
    print("\n🔧 Preparing training data...")
    consumption = df['Consumption'].values
    temperature = df['Temperature'].values
    humidity = df['Humidity'].values
    rainfall = df['Rainfall'].values
    has_classes = df['HasClasses'].values
    day_of_week = df['DayOfWeek'].values
    is_weekend = df['IsWeekend'].values
    
    # Initialize and train model
    print("\n🤖 Training Simplified Model (Ridge Regression)...")
    
    model = SimpleDailyPredictor(sequence_length=7)
    
    model.train(
        consumption, temperature, humidity, rainfall,
        has_classes, day_of_week, is_weekend
    )
    
    print("\n✅ Model trained successfully!")
    
    # Predict next 7 days
    print("\n" + "="*70)
    print("🔮 7-DAY FORECAST")
    print("="*70)
    
    # Get last 7 days
    last_7_days = df.tail(7)
    
    # Get tomorrow's date
    tomorrow = df['Date'].max() + timedelta(days=1)
    
    # Get weather forecast
    weather_7day = get_weather_forecast(days=7)
    
    # Get schedule
    schedule_7day = get_campus_schedule(tomorrow, days=7)
    
    # Prepare past data
    past_data = {
        'consumption': df['Consumption'].values[-7:],
        'temperature': df['Temperature'].values[-7:],
        'humidity': df['Humidity'].values[-7:],
        'rainfall': df['Rainfall'].values[-7:],
        'has_classes': df['HasClasses'].values[-7:],
        'day_of_week': df['DayOfWeek'].values[-7:],
        'is_weekend': df['IsWeekend'].values[-7:],
    }
    
    # Make 7-day prediction
    predictions_7day = model.predict_next_n_days(
        past_data, weather_7day, schedule_7day, n_days=7
    )
    
    print(f"\n{'Date':<12} {'Day':<10} {'Classes':<8} {'Temp':<6} {'Rain':<6} {'Predicted':<12} {'Cost':<12}")
    print("-" * 70)
    
    total_consumption = 0
    total_cost = 0
    cost_per_kwh = 12.383
    
    for i in range(7):
        date = tomorrow + timedelta(days=i)
        day_name = date.strftime('%a')
        has_classes_str = 'Yes' if schedule_7day['has_classes'][i] == 1 else 'No'
        temp = weather_7day['temperature'][i]
        rain = weather_7day['rainfall'][i]
        pred = predictions_7day[i]
        cost = pred * cost_per_kwh
        
        total_consumption += pred
        total_cost += cost
        
        print(f"{date.strftime('%Y-%m-%d'):<12} {day_name:<10} {has_classes_str:<8} "
              f"{temp:>5.1f}° {rain:>5.1f}mm {pred:>10.0f} kWh ₱{cost:>10,.2f}")
    
    print("-" * 70)
    print(f"{'TOTAL':<38} {total_consumption:>10.0f} kWh ₱{total_cost:>10,.2f}")
    print(f"{'AVERAGE/DAY':<38} {total_consumption/7:>10.0f} kWh ₱{total_cost/7:>10,.2f}")
    
    # Budget recommendation
    print("\n💰 WEEKLY BUDGET RECOMMENDATION:")
    buffer = 0.10
    recommended_budget = total_cost * (1 + buffer)
    print(f"   Predicted 7-day cost: ₱{total_cost:,.2f}")
    print(f"   + 10% contingency: ₱{total_cost * buffer:,.2f}")
    print(f"   📍 RECOMMENDED BUDGET: ₱{recommended_budget:,.2f}")
    
    print("\n" + "="*70)
    print("✅ Daily Forecasting Complete!")
    print("="*70)
    
    print("\n💡 Note:")
    print("   This is a simplified version using Ridge Regression.")
    print("   For production use, install TensorFlow and use the full")
    print("   Enhanced LSTM-SVM model in daily_campus_forecast.py")
    
    print("\n💡 Tips:")
    print("   • Replace sample data with your actual daily records")
    print("   • Integrate with OpenWeatherMap API for real weather")
    print("   • Update campus schedule with holidays")
    print("   • Retrain model monthly with new data")


if __name__ == "__main__":
    main()
