"""
Daily Campus Electricity Forecasting
Predicts daily electricity consumption based on:
- Weather conditions (temperature, humidity, rainfall)
- Campus schedule (class days vs no-class days)
- Day of week patterns
"""

import sys
sys.path.append('..')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.models.daily_prediction_model import DailyEnergyPredictor


def load_historical_data(csv_file=None):
    """
    Load historical daily electricity data
    
    CSV format should have columns:
    - Date: YYYY-MM-DD
    - Consumption: Daily kWh or Bill amount
    - Temperature: Average temperature (°C)
    - Humidity: Average humidity (%)
    - Rainfall: Daily rainfall (mm)
    - HasClasses: 1 if classes, 0 if no classes
    """
    if csv_file:
        df = pd.read_csv(csv_file)
        df['Date'] = pd.to_datetime(df['Date'])
        df['DayOfWeek'] = df['Date'].dt.dayofweek
        df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
        return df
    else:
        # EXAMPLE DATA - Replace with your actual data
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
            
            # Temperature effect (higher temp = more AC = more consumption)
            temp = 28 + np.random.normal(0, 3)  # 25-31°C typical
            temp_effect = (temp - 25) * 50  # +50 kWh per degree above 25°C
            
            # Humidity effect
            humidity = 70 + np.random.normal(0, 10)  # 60-80%
            
            # Rainfall effect (rain = less AC)
            rainfall = max(0, np.random.exponential(5))  # 0-20mm typical
            rain_effect = -rainfall * 10  # -10 kWh per mm of rain
            
            # Class schedule effect
            has_classes = 0 if is_weekend else 1
            if has_classes == 0:
                class_effect = -300  # 300 kWh less on no-class days
            else:
                class_effect = 0
            
            # Weekend effect
            weekend_effect = -200 if is_weekend else 0
            
            # Calculate consumption
            consumption = base + temp_effect + rain_effect + class_effect + weekend_effect
            consumption = max(800, consumption + np.random.normal(0, 50))  # Add noise
            
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
    """
    Get weather forecast for next N days
    
    In production, integrate with:
    - OpenWeatherMap API
    - PAGASA API
    - AccuWeather API
    """
    print("⚠️  Using example weather forecast. Integrate with real weather API!\n")
    
    # Example forecast
    forecast = {
        'temperature': 28 + np.random.normal(0, 2, days),  # °C
        'humidity': 70 + np.random.normal(0, 5, days),     # %
        'rainfall': np.maximum(0, np.random.exponential(3, days))  # mm
    }
    
    return forecast


def get_campus_schedule(start_date, days=7):
    """
    Get campus schedule for next N days
    
    Args:
        start_date: Starting date
        days: Number of days
    
    Returns:
        Dict with has_classes, day_of_week, is_weekend arrays
    """
    schedule = {
        'has_classes': [],
        'day_of_week': [],
        'is_weekend': []
    }
    
    current_date = start_date
    for _ in range(days):
        day_of_week = current_date.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Determine if there are classes
        # Customize this based on your campus schedule
        has_classes = 0 if is_weekend else 1
        
        # Check for holidays (add your campus holidays here)
        holidays = [
            '2024-12-25',  # Christmas
            '2024-12-26',  # Boxing Day
            '2025-01-01',  # New Year
            # Add more holidays
        ]
        
        if current_date.strftime('%Y-%m-%d') in holidays:
            has_classes = 0
        
        schedule['has_classes'].append(has_classes)
        schedule['day_of_week'].append(day_of_week)
        schedule['is_weekend'].append(is_weekend)
        
        current_date += timedelta(days=1)
    
    return {k: np.array(v) for k, v in schedule.items()}


def main():
    print("="*70)
    print("DAILY CAMPUS ELECTRICITY FORECASTING")
    print("Weather-Aware & Schedule-Aware Predictions")
    print("="*70)
    
    # Load historical data
    print("\n📊 Loading historical data...")
    df = load_historical_data()
    
    print(f"   Data range: {df['Date'].min().date()} to {df['Date'].max().date()}")
    print(f"   Total days: {len(df)}")
    print(f"   Average consumption: {df['Consumption'].mean():.0f} kWh/day")
    print(f"   Class days: {df['HasClasses'].sum()} days")
    print(f"   No-class days: {(1-df['HasClasses']).sum()} days")
    
    # Show consumption patterns
    print("\n📈 Consumption Patterns:")
    class_days = df[df['HasClasses'] == 1]['Consumption'].mean()
    no_class_days = df[df['HasClasses'] == 0]['Consumption'].mean()
    weekdays = df[df['IsWeekend'] == 0]['Consumption'].mean()
    weekends = df[df['IsWeekend'] == 1]['Consumption'].mean()
    
    print(f"   Class days average: {class_days:.0f} kWh/day")
    print(f"   No-class days average: {no_class_days:.0f} kWh/day")
    print(f"   Difference: {class_days - no_class_days:.0f} kWh/day ({((class_days-no_class_days)/no_class_days*100):.1f}%)")
    print(f"   Weekdays average: {weekdays:.0f} kWh/day")
    print(f"   Weekends average: {weekends:.0f} kWh/day")
    
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
    print("\n🤖 Training Enhanced LSTM-SVM Model...")
    print("   This will take a few minutes...")
    
    model = DailyEnergyPredictor(
        sequence_length=7,  # Use past 7 days
        lstm_weight=0.7     # 70% LSTM, 30% SVM
    )
    
    model.train(
        consumption, temperature, humidity, rainfall,
        has_classes, day_of_week, is_weekend,
        epochs=100,
        validation_split=0.2
    )
    
    print("\n✅ Model trained successfully!")
    
    # Predict tomorrow
    print("\n" + "="*70)
    print("🔮 PREDICTING TOMORROW'S CONSUMPTION")
    print("="*70)
    
    # Get last 7 days of data
    last_7_days = df.tail(7)
    
    # Get tomorrow's date
    tomorrow = df['Date'].max() + timedelta(days=1)
    tomorrow_day_of_week = tomorrow.weekday()
    tomorrow_is_weekend = 1 if tomorrow_day_of_week >= 5 else 0
    
    # Get weather forecast for tomorrow
    weather_forecast = get_weather_forecast(days=1)
    
    # Get schedule for tomorrow
    tomorrow_has_classes = 0 if tomorrow_is_weekend else 1
    
    print(f"\n📅 Date: {tomorrow.strftime('%A, %B %d, %Y')}")
    print(f"   Day type: {'Weekend' if tomorrow_is_weekend else 'Weekday'}")
    print(f"   Classes: {'No' if tomorrow_has_classes == 0 else 'Yes'}")
    print(f"\n🌤️  Weather Forecast:")
    print(f"   Temperature: {weather_forecast['temperature'][0]:.1f}°C")
    print(f"   Humidity: {weather_forecast['humidity'][0]:.0f}%")
    print(f"   Rainfall: {weather_forecast['rainfall'][0]:.1f}mm")
    
    # Make prediction
    prediction = model.predict_single_day(
        last_7_days['Consumption'].values,
        last_7_days['Temperature'].values,
        last_7_days['Humidity'].values,
        last_7_days['Rainfall'].values,
        last_7_days['HasClasses'].values,
        last_7_days['DayOfWeek'].values,
        last_7_days['IsWeekend'].values,
        weather_forecast['temperature'][0],
        weather_forecast['humidity'][0],
        weather_forecast['rainfall'][0],
        tomorrow_has_classes,
        tomorrow_day_of_week,
        tomorrow_is_weekend
    )
    
    print(f"\n⚡ PREDICTED CONSUMPTION: {prediction:.0f} kWh")
    
    # Convert to cost (₱12.383 per kWh)
    cost_per_kwh = 12.383
    predicted_cost = prediction * cost_per_kwh
    print(f"💰 PREDICTED COST: ₱{predicted_cost:,.2f}")
    
    # Compare with similar days
    similar_days = df[
        (df['HasClasses'] == tomorrow_has_classes) & 
        (df['IsWeekend'] == tomorrow_is_weekend)
    ]
    avg_similar = similar_days['Consumption'].mean()
    
    print(f"\n📊 Comparison:")
    print(f"   Average for similar days: {avg_similar:.0f} kWh")
    print(f"   Difference: {prediction - avg_similar:+.0f} kWh ({((prediction-avg_similar)/avg_similar*100):+.1f}%)")
    
    # Predict next 7 days
    print("\n" + "="*70)
    print("🔮 7-DAY FORECAST")
    print("="*70)
    
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
    buffer = 0.10  # 10% buffer
    recommended_budget = total_cost * (1 + buffer)
    print(f"   Predicted 7-day cost: ₱{total_cost:,.2f}")
    print(f"   + 10% contingency: ₱{total_cost * buffer:,.2f}")
    print(f"   📍 RECOMMENDED BUDGET: ₱{recommended_budget:,.2f}")
    
    print("\n" + "="*70)
    print("✅ Daily Forecasting Complete!")
    print("="*70)
    
    print("\n💡 Tips:")
    print("   • Update weather forecast daily for best accuracy")
    print("   • Mark special events (exams, holidays) in schedule")
    print("   • Monitor actual vs predicted to improve model")
    print("   • Retrain model monthly with new data")


if __name__ == "__main__":
    main()
