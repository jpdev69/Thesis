# Backend API

FastAPI backend for the Campus Energy Forecasting System.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Or with uvicorn:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - API information
- `POST /train` - Train model with energy data
- `POST /predict` - Single-step predictions
- `POST /forecast` - Multi-step forecast
- `GET /health` - Health check

## Example Request

```bash
curl -X POST "http://localhost:8000/train" \
  -H "Content-Type: application/json" \
  -d '{"values": [100, 120, 115, 130, 125], "sequence_length": 24}'
```
