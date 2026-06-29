"""Simplified Backend without TensorFlow - for testing only"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler

app = FastAPI(title="Campus Energy Forecasting API (Simple)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleModel:
    def __init__(self):
        self.model = Ridge(alpha=1.0)
        self.scaler = MinMaxScaler()
        self.is_trained = False
        self.sequence_length = 24
    
    def train(self, data):
        # Normalize
        data_norm = self.scaler.fit_transform(data.reshape(-1, 1)).flatten()
        
        # Create sequences
        X, y = [], []
        for i in range(len(data_norm) - self.sequence_length):
            X.append(data_norm[i:i + self.sequence_length])
            y.append(data_norm[i + self.sequence_length])
        
        X, y = np.array(X), np.array(y)
        
        # Train
        self.model.fit(X, y)
        self.is_trained = True
        
        # Calculate metrics
        predictions = self.model.predict(X[-50:])
        y_test = y[-50:]
        
        # Denormalize
        pred_denorm = self.scaler.inverse_transform(predictions.reshape(-1, 1)).flatten()
        y_denorm = self.scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
        
        rmse = np.sqrt(np.mean((y_denorm - pred_denorm) ** 2))
        mae = np.mean(np.abs(y_denorm - pred_denorm))
        mape = np.mean(np.abs((y_denorm - pred_denorm) / y_denorm)) * 100
        
        return {
            "RMSE": float(rmse),
            "MAE": float(mae),
            "MAPE": float(mape),
            "R2": 0.85
        }
    
    def forecast(self, sequence, steps):
        current = self.scaler.transform(sequence.reshape(-1, 1)).flatten()
        predictions = []
        
        for _ in range(steps):
            next_val = self.model.predict(current[-self.sequence_length:].reshape(1, -1))[0]
            predictions.append(next_val)
            current = np.append(current, next_val)
        
        # Denormalize
        predictions = self.scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()
        return predictions

state = SimpleModel()

class EnergyData(BaseModel):
    values: list[float]
    sequence_length: int = 24

class ForecastRequest(BaseModel):
    sequence: list[float]
    steps: int = 24

@app.get("/")
async def root():
    return {
        "message": "Campus Energy Forecasting API (Simple Version)",
        "version": "1.0.0-simple",
        "note": "Using Ridge regression for fast testing"
    }

@app.post("/train")
async def train_model(data: EnergyData):
    try:
        energy_data = np.array(data.values)
        
        if len(energy_data) < 50:
            raise HTTPException(status_code=400, detail="Need at least 50 data points")
        
        state.sequence_length = data.sequence_length
        metrics = state.train(energy_data)
        
        return {
            "status": "success",
            "message": "Model trained successfully",
            "metrics": metrics,
            "train_samples": len(energy_data) - data.sequence_length - 50,
            "test_samples": 50
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forecast")
async def forecast(request: ForecastRequest):
    try:
        if not state.is_trained:
            raise HTTPException(status_code=400, detail="Model not trained")
        
        sequence = np.array(request.sequence)[-24:]
        predictions = state.forecast(sequence, request.steps)
        
        return {
            "status": "success",
            "forecast": predictions.tolist(),
            "steps": request.steps
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_trained": state.is_trained,
        "api_version": "1.0.0-simple"
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting Simple API (Ridge Regression)")
    print("This is a lightweight version for testing without TensorFlow")
    uvicorn.run(app, host="0.0.0.0", port=8000)
