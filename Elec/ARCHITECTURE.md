# 🏗️ System Architecture

## Overview

The Daily Energy Forecasting System uses a hybrid AI/ML approach combining Enhanced LSTM with attention mechanism and SVM for weather-aware and schedule-aware predictions.

---

## 🎯 System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION                          │
├─────────────────────────────────────────────────────────────────┤
│  • Daily Consumption (kWh)                                      │
│  • Weather (Temperature, Humidity, Rainfall)                    │
│  • Schedule (Class Days, Weekends, Holidays)                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA PREPROCESSING                          │
├─────────────────────────────────────────────────────────────────┤
│  • Normalization (MinMax Scaling)                               │
│  • Feature Engineering (Cyclical Encoding)                      │
│  • Sequence Creation (7-day windows)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ENHANCED LSTM-SVM MODEL                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          LSTM Component (Feature Extraction)             │  │
│  │  • Layer 1: LSTM(128) + BatchNorm + Dropout(0.3)        │  │
│  │  • Layer 2: LSTM(64) + BatchNorm + Dropout(0.3)         │  │
│  │  • Attention Mechanism (Weather-Aware)                   │  │
│  │  • Dense(32) + Dropout(0.2)                              │  │
│  │  • Output: Predicted Consumption                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         SVM Component (Final Prediction)                 │  │
│  │  • Kernel: RBF                                           │  │
│  │  • Input: Flattened Sequence + LSTM Features            │  │
│  │  • Purpose: Residual Correction                          │  │
│  │  • Output: Refined Prediction                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Weighted Ensemble                              │  │
│  │  Final = 0.7 × LSTM + 0.3 × SVM                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FORECASTING ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│  • Single Day Prediction                                        │
│  • Multi-Day Forecasting (Recursive)                            │
│  • Confidence Intervals                                         │
│  • Cost Calculations (₱12.383/kWh)                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                  │
├─────────────────────────────────────────────────────────────────┤
│  • Daily Consumption Predictions                                │
│  • 7-Day Forecasts                                              │
│  • Cost Estimates                                               │
│  • Budget Recommendations                                       │
│  • Performance Metrics                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Model Architecture

### Input Features (8 total)

```python
features = [
    consumption_normalized,    # Historical consumption
    temperature_normalized,    # Weather: Temperature (°C)
    humidity_normalized,       # Weather: Humidity (%)
    rainfall_normalized,       # Weather: Rainfall (mm)
    has_classes,              # Schedule: Binary (1=yes, 0=no)
    is_weekend,               # Schedule: Binary (1=weekend, 0=weekday)
    day_sin,                  # Temporal: sin(2π × day/7)
    day_cos                   # Temporal: cos(2π × day/7)
]
```

### LSTM Component

```
Input: (batch_size, 7, 8)  # 7 days, 8 features

LSTM Layer 1:
  ├─ LSTM(128 units, return_sequences=True)
  ├─ BatchNormalization()
  └─ Dropout(0.3)

LSTM Layer 2:
  ├─ LSTM(64 units, return_sequences=True)
  ├─ BatchNormalization()
  └─ Dropout(0.3)

Attention Mechanism:
  ├─ Dense(1, activation='tanh')  # Attention scores
  ├─ Softmax()                     # Attention weights
  └─ Weighted Sum                  # Context vector

Dense Layers:
  ├─ Dense(32, activation='relu')
  ├─ Dropout(0.2)
  └─ Dense(1)  # Output

Output: (batch_size, 1)  # Predicted consumption
```

### SVM Component

```
Input: Flattened sequence (7×8=56) + LSTM prediction (1) = 57 features

SVM:
  ├─ Kernel: RBF (Radial Basis Function)
  ├─ C: 100 (Regularization)
  ├─ Epsilon: 0.01 (Tube width)
  └─ Gamma: 'scale' (Kernel coefficient)

Output: Residual correction
```

### Ensemble

```python
final_prediction = 0.7 × lstm_prediction + 0.3 × svm_prediction
```

---

## 📊 Data Flow

### Training Phase

```
Historical Data (90 days)
    │
    ├─ Normalize consumption & weather
    ├─ Encode schedule & temporal features
    └─ Create sequences (7-day windows)
    │
    ▼
Training Set (70%)
    │
    ├─ Train LSTM (100 epochs)
    │   ├─ Early stopping (patience=15)
    │   └─ Learning rate reduction (patience=7)
    │
    ├─ Get LSTM predictions
    │
    └─ Train SVM on residuals
    │
    ▼
Validation Set (20%)
    │
    └─ Evaluate metrics (RMSE, MAE, MAPE, R²)
    │
    ▼
Trained Model
```

### Prediction Phase

```
Past 7 Days Data
    │
    ├─ Consumption history
    ├─ Weather history
    └─ Schedule history
    │
    ▼
Future Weather Forecast
    │
    ├─ Temperature (7 days)
    ├─ Humidity (7 days)
    └─ Rainfall (7 days)
    │
    ▼
Future Schedule
    │
    ├─ Class days (7 days)
    ├─ Weekends (7 days)
    └─ Holidays (7 days)
    │
    ▼
Model Prediction
    │
    ├─ Day 1: Past 7 days → Predict Day 1
    ├─ Day 2: Past 6 days + Day 1 → Predict Day 2
    ├─ Day 3: Past 5 days + Day 1-2 → Predict Day 3
    └─ ...
    │
    ▼
7-Day Forecast
    │
    ├─ Daily consumption (kWh)
    ├─ Daily cost (₱)
    └─ Budget recommendation
```

---

## 🔧 Component Details

### 1. Data Preprocessor (`src/data/preprocessor.py`)

**Responsibilities:**
- Load and validate data
- Handle missing values
- Normalize features
- Create sequences
- Split train/validation sets

**Key Methods:**
```python
normalize(data)           # MinMax scaling
create_sequences(data)    # 7-day windows
split_data(X, y)         # Train/validation split
```

### 2. Daily Prediction Model (`src/models/daily_prediction_model.py`)

**Responsibilities:**
- Build LSTM architecture
- Build SVM model
- Train hybrid ensemble
- Generate predictions
- Calculate metrics

**Key Methods:**
```python
train(consumption, temperature, ...)  # Train model
predict_single_day(past_data, ...)   # Predict tomorrow
predict_next_n_days(past_data, ...)  # Multi-day forecast
```

### 3. Enhanced LSTM (`src/models/enhanced_lstm.py`)

**Responsibilities:**
- LSTM architecture with attention
- Batch normalization
- Dropout regularization
- Training callbacks

**Key Methods:**
```python
_build_model()           # Create architecture
train(X, y)             # Train LSTM
predict(X)              # Generate predictions
```

### 4. Hybrid Model (`src/models/hybrid_model.py`)

**Responsibilities:**
- Combine LSTM and SVM
- Weighted ensemble
- Model management

**Key Methods:**
```python
train(X, y)             # Train both components
predict(X)              # Ensemble prediction
```

### 5. Forecasting Engine (`src/forecasting/forecaster.py`)

**Responsibilities:**
- Single-step forecasting
- Multi-step forecasting
- Confidence intervals
- Recursive predictions

**Key Methods:**
```python
forecast_single_step(X)              # One day ahead
forecast_multi_step(X, steps)        # N days ahead
forecast_with_confidence(X)          # With intervals
```

### 6. Backend API (`backend/daily_api.py`)

**Responsibilities:**
- REST API endpoints
- Model training
- Forecast generation
- Status monitoring

**Endpoints:**
```
POST /train-daily       # Train model
POST /forecast-daily    # Generate forecast
GET  /model-status      # Check status
GET  /health           # Health check
```

### 7. Frontend Dashboard (`frontend/`)

**Responsibilities:**
- User interface
- Data visualization
- Authentication
- Theme management

**Pages:**
```
login.html      # Authentication
dashboard.html  # Main overview
analytics.html  # Detailed insights
models.html     # Model management
reports.html    # Report generation
settings.html   # Configuration
admin.html      # User approval
```

---

## 🌤️ Weather Integration

### Data Sources

```
┌─────────────────────────────────────────────────────────────┐
│                    Weather Data Sources                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. OpenWeatherMap API (Recommended)                        │
│     ├─ Free tier: 1000 calls/day                           │
│     ├─ 7-day forecast                                       │
│     ├─ Historical data                                      │
│     └─ Temperature, humidity, rainfall                      │
│                                                             │
│  2. PAGASA (Philippine Weather Service)                     │
│     ├─ Official weather data                                │
│     ├─ 5-day forecast                                       │
│     └─ Manual input required                                │
│                                                             │
│  3. Campus Weather Station                                  │
│     ├─ Most accurate for location                           │
│     ├─ Real-time data                                       │
│     └─ Requires hardware setup                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Weather Impact Model

```python
# Temperature effect
temp_effect = (temperature - 25) × 50  # kWh per °C above 25°C

# Humidity effect
humidity_effect = (humidity - 70) × 2  # kWh per % above 70%

# Rainfall effect
rainfall_effect = -rainfall × 10  # kWh per mm (negative = less AC)

# Total weather impact
weather_impact = temp_effect + humidity_effect + rainfall_effect
```

---

## 📚 Schedule Integration

### Schedule Definition

```python
def get_campus_schedule(date):
    day_of_week = date.weekday()  # 0=Monday, 6=Sunday
    
    # Weekend check
    if day_of_week >= 5:
        return 0  # No classes
    
    # Holiday check
    holidays = [
        '2024-12-25',  # Christmas
        '2025-01-01',  # New Year
        # Add more...
    ]
    
    if date.strftime('%Y-%m-%d') in holidays:
        return 0  # No classes
    
    # Regular class day
    return 1
```

### Schedule Impact Model

```python
# Class day effect
if has_classes == 1:
    class_effect = 0  # Baseline
else:
    class_effect = -300  # -300 kWh on no-class days

# Weekend effect
if is_weekend == 1:
    weekend_effect = -200  # Additional -200 kWh
else:
    weekend_effect = 0

# Total schedule impact
schedule_impact = class_effect + weekend_effect
```

---

## 📊 Performance Metrics

### Evaluation Metrics

```python
# Root Mean Square Error
RMSE = sqrt(mean((actual - predicted)²))

# Mean Absolute Error
MAE = mean(|actual - predicted|)

# Mean Absolute Percentage Error
MAPE = mean(|actual - predicted| / actual) × 100

# R² Score (Coefficient of Determination)
R² = 1 - (SS_res / SS_tot)
```

### Target Performance

| Metric | Formula | Target | Excellent |
|--------|---------|--------|-----------|
| **RMSE** | √(Σ(y-ŷ)²/n) | < 100 kWh | < 50 kWh |
| **MAE** | Σ\|y-ŷ\|/n | < 80 kWh | < 40 kWh |
| **MAPE** | Σ\|y-ŷ\|/y/n×100 | < 8% | < 5% |
| **R²** | 1-SS_res/SS_tot | > 0.85 | > 0.92 |

---

## 🔄 System Workflow

### Daily Operation

```
06:00 AM - Collect yesterday's data
    ├─ Consumption from meter
    ├─ Weather from API
    └─ Schedule from calendar

07:00 AM - Update weather forecast
    └─ Get 7-day forecast from API

08:00 AM - Generate predictions
    ├─ Predict today's consumption
    ├─ Generate 7-day forecast
    └─ Calculate budget

09:00 AM - Send notifications
    ├─ Daily prediction
    ├─ High-load warnings
    └─ Budget alerts

Throughout day - Monitor actual vs predicted
    └─ Log deviations

11:00 PM - Daily summary
    ├─ Actual vs predicted
    ├─ Accuracy metrics
    └─ Insights for tomorrow
```

### Monthly Maintenance

```
1st of Month:
    ├─ Retrain model with new data
    ├─ Evaluate performance
    └─ Update parameters

Weekly:
    ├─ Review accuracy
    ├─ Check weather API
    └─ Update holiday calendar

As needed:
    ├─ Adjust for special events
    ├─ Handle equipment changes
    └─ Optimize model parameters
```

---

## 🎯 Design Decisions

### Why Enhanced LSTM-SVM Hybrid?

**LSTM Advantages:**
- ✅ Captures temporal patterns
- ✅ Learns seasonal trends
- ✅ Handles sequential data
- ✅ Attention for weather awareness

**SVM Advantages:**
- ✅ Robust to outliers
- ✅ Non-linear relationships
- ✅ Residual correction
- ✅ Stable predictions

**Hybrid Benefits:**
- ✅ Best of both worlds
- ✅ Higher accuracy
- ✅ More robust
- ✅ Better generalization

### Why 7-Day Sequence Length?

- ✅ Captures weekly patterns
- ✅ Includes weekend effects
- ✅ Sufficient context
- ✅ Not too long (overfitting)
- ✅ Practical for forecasting

### 100% Integrated Hybrid Architecture

- ✅ LSTM extracts temporal features
- ✅ SVM learns on integrated features  
- ✅ True hybrid (not weighted averaging)
- ✅ Both models contribute equally
- ✅ Feature stacking architecture

---

## 🚀 Scalability

### Current Capacity

- **Data Points:** Up to 1000 days
- **Training Time:** 5-10 minutes
- **Prediction Time:** < 1 second
- **API Throughput:** 100 requests/minute

### Future Enhancements

1. **Multi-Campus Support**
   - Federated learning
   - Campus-specific models
   - Shared knowledge

2. **Real-Time Monitoring**
   - IoT integration
   - Live consumption tracking
   - Instant alerts

3. **Advanced Features**
   - Anomaly detection
   - Equipment diagnostics
   - Optimization recommendations

4. **Mobile App**
   - iOS/Android apps
   - Push notifications
   - Mobile dashboard

---

## 📚 Technology Stack

### Backend
- **Python 3.8+**
- **TensorFlow 2.x** - Deep learning
- **scikit-learn** - SVM and preprocessing
- **FastAPI** - REST API
- **NumPy** - Numerical computing
- **Pandas** - Data manipulation

### Frontend
- **HTML5/CSS3** - Structure and styling
- **JavaScript (ES6+)** - Interactivity
- **Chart.js** - Data visualization
- **Inter Font** - Typography

### Data
- **CSV** - Data storage
- **JSON** - API communication
- **YAML** - Configuration

---

**This architecture provides a robust, scalable, and accurate system for daily energy forecasting with weather and schedule awareness.** 🏗️✅
