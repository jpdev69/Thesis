"""
Daily Energy Prediction API
Supports weather-aware and schedule-aware predictions
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import sys
sys.path.append('..')

from src.models.daily_prediction_model import DailyEnergyPredictor

app = FastAPI(title="Daily Campus Energy Forecasting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model state
model_state = {
    'model': None,
    'is_trained': False,
    'last_trained': None
}


class DailyTrainingData(BaseModel):
    consumption: list[float]
    temperature: list[float]
    humidity: list[float]
    rainfall: list[float]
    has_classes: list[int]
    day_of_week: list[int]
    is_weekend: list[int]
    epochs: int = 100


class DailyForecastRequest(BaseModel):
    past_data: dict  # consumption, temperature, humidity, rainfall, has_classes, day_of_week, is_weekend
    future_weather: dict  # temperature, humidity, rainfall
    future_schedule: dict  # has_classes, day_of_week, is_weekend
    n_days: int = 7


@app.get("/")
async def root():
    return {
        "message": "Daily Campus Energy Forecasting API",
        "version": "2.0.0",
        "features": ["weather-aware", "schedule-aware", "daily-predictions"],
        "model": "Enhanced LSTM-SVM Hybrid"
    }


@app.post("/train-daily")
async def train_daily_model(data: DailyTrainingData):
    """Train the daily prediction model with weather and schedule data"""
    try:
        # Validate data
        if len(data.consumption) < 30:
            raise HTTPException(
                status_code=400,
                detail="Need at least 30 days of data for training"
            )
        
        # Check all arrays have same length
        lengths = [
            len(data.consumption), len(data.temperature), len(data.humidity),
            len(data.rainfall), len(data.has_classes), len(data.day_of_week),
            len(data.is_weekend)
        ]
        if len(set(lengths)) != 1:
            raise HTTPException(
                status_code=400,
                detail="All data arrays must have the same length"
            )
        
        # Convert to numpy arrays
        consumption = np.array(data.consumption)
        temperature = np.array(data.temperature)
        humidity = np.array(data.humidity)
        rainfall = np.array(data.rainfall)
        has_classes = np.array(data.has_classes)
        day_of_week = np.array(data.day_of_week)
        is_weekend = np.array(data.is_weekend)
        
        # Initialize and train model
        model = DailyEnergyPredictor(sequence_length=7, lstm_weight=0.7)
        
        history = model.train(
            consumption, temperature, humidity, rainfall,
            has_classes, day_of_week, is_weekend,
            epochs=data.epochs,
            validation_split=0.2
        )
        
        # Store model
        model_state['model'] = model
        model_state['is_trained'] = True
        
        from datetime import datetime
        model_state['last_trained'] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "message": "Daily prediction model trained successfully",
            "data_points": len(consumption),
            "training_days": len(consumption),
            "last_trained": model_state['last_trained']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/forecast-daily")
async def forecast_daily(request: DailyForecastRequest):
    """Generate daily forecasts for next N days"""
    try:
        if not model_state['is_trained']:
            raise HTTPException(
                status_code=400,
                detail="Model not trained. Please train the model first."
            )
        
        model = model_state['model']
        
        # Convert to numpy arrays
        past_data = {
            k: np.array(v) for k, v in request.past_data.items()
        }
        future_weather = {
            k: np.array(v) for k, v in request.future_weather.items()
        }
        future_schedule = {
            k: np.array(v) for k, v in request.future_schedule.items()
        }
        
        # Make predictions
        predictions = model.predict_next_n_days(
            past_data,
            future_weather,
            future_schedule,
            n_days=request.n_days
        )
        
        # Calculate costs (₱12.383 per kWh)
        cost_per_kwh = 12.383
        costs = predictions * cost_per_kwh
        
        return {
            "status": "success",
            "predictions": predictions.tolist(),
            "costs": costs.tolist(),
            "n_days": request.n_days,
            "total_consumption": float(predictions.sum()),
            "total_cost": float(costs.sum()),
            "avg_daily_consumption": float(predictions.mean()),
            "avg_daily_cost": float(costs.mean())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model-status")
async def model_status():
    """Get current model status"""
    return {
        "is_trained": model_state['is_trained'],
        "last_trained": model_state['last_trained'],
        "model_type": "Enhanced LSTM-SVM Hybrid",
        "features": [
            "consumption",
            "temperature",
            "humidity",
            "rainfall",
            "has_classes",
            "day_of_week",
            "is_weekend"
        ]
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_trained": model_state['is_trained'],
        "api_version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    print("="*70)
    print("Daily Campus Energy Forecasting API")
    print("Weather-Aware & Schedule-Aware Predictions")
    print("="*70)
    print("\nStarting server on http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nFeatures:")
    print("  ✓ Daily consumption predictions")
    print("  ✓ Weather integration (temperature, humidity, rainfall)")
    print("  ✓ Class schedule awareness")
    print("  ✓ Enhanced LSTM-SVM hybrid model")
    print("="*70)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
