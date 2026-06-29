"""FastAPI Backend for Energy Forecasting System"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.hybrid_model import HybridLSTMSVM
from src.data.preprocessor import EnergyDataPreprocessor
from src.forecasting.forecaster import EnergyForecaster
from src.evaluation.metrics import ForecastingMetrics

app = FastAPI(title="Campus Energy Forecasting API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class ModelState:
    def __init__(self):
        self.model = None
        self.preprocessor = None
        self.forecaster = None
        self.is_trained = False

state = ModelState()


class EnergyData(BaseModel):
    values: list[float]
    sequence_length: int = 24


class ForecastRequest(BaseModel):
    sequence: list[float]
    steps: int = 24


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("Energy Forecasting API started")
    print("Waiting for model training...")


@app.get("/")
async def root():
    return {
        "message": "Campus Energy Forecasting API",
        "version": "1.0.0",
        "endpoints": ["/train", "/predict", "/forecast", "/metrics"]
    }


@app.post("/train")
async def train_model(data: EnergyData):
    """Train the model with provided data"""
    try:
        energy_data = np.array(data.values)
        
        if len(energy_data) < 50:
            raise HTTPException(status_code=400, detail="Need at least 50 data points")
        
        # Initialize fresh preprocessor and model
        state.preprocessor = EnergyDataPreprocessor(sequence_length=data.sequence_length)
        state.model = HybridLSTMSVM(sequence_length=data.sequence_length, features=1)
        
        # Preprocess
        data_norm = state.preprocessor.normalize(energy_data)
        X, y = state.preprocessor.create_sequences(data_norm)
        X = X.reshape(X.shape[0], X.shape[1], 1)
        
        if len(X) < 10:
            raise HTTPException(status_code=400, detail="Not enough sequences for training")
        
        # Split
        train_size = int(0.8 * len(X))
        X_train, y_train = X[:train_size], y[:train_size]
        X_test, y_test = X[train_size:], y[train_size:]
        
        # Train with fewer epochs for faster response
        print(f"Training model with {len(X_train)} samples...")
        state.model.train(X_train, y_train, epochs=15)
        
        # Evaluate
        predictions = state.model.predict(X_test)
        y_test_denorm = state.preprocessor.denormalize(y_test)
        pred_denorm = state.preprocessor.denormalize(predictions)
        
        metrics = ForecastingMetrics.calculate_all_metrics(y_test_denorm, pred_denorm)
        
        # Create forecaster
        state.forecaster = EnergyForecaster(state.model, state.preprocessor)
        state.is_trained = True
        
        print("Training completed successfully")
        
        return {
            "status": "success",
            "message": "Model trained successfully",
            "metrics": metrics,
            "train_samples": len(X_train),
            "test_samples": len(X_test)
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Training error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@app.post("/predict")
async def predict(data: EnergyData):
    """Make single-step predictions"""
    try:
        if not state.is_trained:
            raise HTTPException(status_code=400, detail="Model not trained. Please train the model first.")
        
        energy_data = np.array(data.values)
        data_norm = state.preprocessor.normalize(energy_data)
        X, _ = state.preprocessor.create_sequences(data_norm)
        X = X.reshape(X.shape[0], X.shape[1], 1)
        
        predictions = state.forecaster.forecast_single_step(X)
        
        return {
            "status": "success",
            "predictions": predictions.tolist()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/forecast")
async def forecast(request: ForecastRequest):
    """Multi-step ahead forecast"""
    try:
        if not state.is_trained:
            raise HTTPException(status_code=400, detail="Model not trained. Please train the model first.")
        
        sequence = np.array(request.sequence)
        
        if len(sequence) < 24:
            raise HTTPException(status_code=400, detail="Need at least 24 data points for forecasting")
        
        # Use last 24 values
        sequence = sequence[-24:]
        
        # Normalize using the same scaler from training
        sequence_norm = state.preprocessor.normalize(sequence)
        
        # Forecast
        predictions = state.forecaster.forecast_multi_step(sequence_norm, steps=request.steps)
        
        return {
            "status": "success",
            "forecast": predictions.tolist(),
            "steps": request.steps
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Forecast error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_trained": state.is_trained,
        "api_version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
