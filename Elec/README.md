# ⚡ EnergyAI - Daily Energy Forecasting Platform

A complete **daily energy forecasting system** with weather-aware and schedule-aware AI predictions for campus electricity management.

## 🎯 System Goal

**Predict daily electricity consumption based on weather conditions and class schedule for accurate budget planning and energy optimization.**

---

## 🌟 Key Features

- 🤖 **Daily Predictions** - Weather-aware and schedule-aware forecasting
- 🌤️ **Weather Integration** - Temperature, humidity, rainfall
- 📚 **Schedule Awareness** - Class days vs no-class days
- 🧠 **Enhanced LSTM-SVM** - Hybrid model with attention mechanism
- 📊 **7-Day Forecasting** - Multi-step ahead predictions
- 💰 **Cost Calculation** - Philippine Peso (₱12.383 per kWh)
- 📈 **Budget Planning** - Automatic recommendations
- 🔐 **User Authentication** - Secure login with admin approval
- 🌓 **Light/Dark Theme** - Comfortable viewing
- 🌱 **Eco-Friendly Design** - Green theme

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 2: Run Daily Forecast Example

```bash
cd examples
python daily_campus_forecast.py
```

**Output:**
- Tomorrow's consumption prediction
- 7-day forecast
- Cost estimates
- Budget recommendations

### Step 3: Start Web Dashboard

```bash
python -m http.server 8080 --directory frontend
# Open: http://localhost:8080/login.html
```

**Login:**
- Create account → Admin approval (password: `admin123`) → Login

---

## 📊 What Makes This System Unique

### Weather-Aware Predictions

The system integrates real weather data:
- **Temperature** - Higher temp = more AC usage (+50 kWh per °C above 25°C)
- **Humidity** - Higher humidity = more AC usage (+20 kWh per 10% above 70%)
- **Rainfall** - Rain = less AC needed (-10 kWh per mm)

### Schedule-Aware Predictions

The system considers campus schedule:
- **Class Days** - Baseline consumption (100%)
- **No-Class Days** - Reduced consumption (-20%)
- **Weekends** - Minimal consumption (-27%)

### Enhanced LSTM-SVM Hybrid

- **LSTM Component** - Extracts temporal features with attention mechanism
- **SVM Component** - Learns non-linear patterns on LSTM features
- **Integration** - True 100% hybrid through feature stacking (not weighted averaging)
- **Architecture** - Input → LSTM(features) → LSTM+Stats → SVM → Output

---

## 📁 Project Structure

```
EnergyAI/
├── src/
│   ├── models/
│   │   ├── daily_prediction_model.py  ⭐ Main daily prediction model
│   │   ├── enhanced_lstm.py           Enhanced LSTM with attention
│   │   ├── hybrid_model.py            LSTM-SVM hybrid
│   │   ├── lstm_model.py              Basic LSTM
│   │   └── svm_model.py               SVM model
│   ├── data/
│   │   └── preprocessor.py            Data preprocessing
│   ├── evaluation/
│   │   └── metrics.py                 Performance metrics
│   ├── federated/
│   │   └── aggregator.py              Federated learning
│   └── forecasting/
│       └── forecaster.py              Forecasting engine
├── examples/
│   ├── daily_campus_forecast.py  ⭐ Main daily prediction script
│   ├── campus_bill_forecast.py       Monthly bill predictions
│   ├── enhanced_forecast.py          Enhanced model demo
│   ├── basic_forecast.py             Basic LSTM demo
│   └── federated_training.py         Federated learning demo
├── frontend/
│   ├── dashboard.html                Main dashboard
│   ├── analytics.html                Analytics page
│   ├── models.html                   Model management
│   ├── reports.html                  Reports page
│   ├── settings.html                 Settings page
│   ├── login.html                    Authentication
│   ├── admin.html                    Admin panel
│   ├── dashboard.js                  Dashboard logic
│   ├── dashboard.css                 Styles
│   └── auth.js                       Authentication logic
├── backend/
│   ├── daily_api.py              ⭐ Daily prediction API
│   ├── simple_app.py                 Simple API (testing)
│   └── app.py                        Full API
├── data/
│   ├── daily_campus_template.csv ⭐ Daily data template
│   └── campus_bills_template.csv     Monthly bills template
├── config/
│   └── config.yaml                   Configuration
├── DAILY_PREDICTION_GUIDE.md     ⭐ Complete guide (15+ pages)
├── START_HERE.md                 ⭐ Quick start guide
├── ARCHITECTURE.md                   System architecture
├── SYSTEM_STATUS.md                  Status report
├── QUICK_REFERENCE.md                Quick reference
├── COMPLETION_SUMMARY.md             Completion summary
├── HOW_TO_USE_REAL_DATA.md          Real data guide
├── CLEAN_SETUP.md                    Installation guide
├── FINAL_SYSTEM.md                   System documentation
└── requirements.txt                  Python dependencies
```

---

## 📊 Using Your Real Data

### Data Requirements

**Minimum:** 30 days of daily data  
**Recommended:** 90+ days for best accuracy

**Required for each day:**
- Date (YYYY-MM-DD)
- Consumption (kWh or ₱)
- Temperature (°C)
- Humidity (%)
- Rainfall (mm)
- HasClasses (1=yes, 0=no)

### Data Template

Use `data/daily_campus_template.csv`:

```csv
Date,Consumption,Temperature,Humidity,Rainfall,HasClasses
2024-09-01,1450,28.5,72,0,1
2024-09-02,1520,29.2,68,0,1
2024-09-03,1480,27.8,75,5.2,1
```

### Where to Get Data

| Data | Source |
|------|--------|
| **Consumption** | Electric meter (daily kWh reading) |
| **Temperature** | Weather station / OpenWeatherMap API |
| **Humidity** | Weather station / OpenWeatherMap API |
| **Rainfall** | Weather station / PAGASA |
| **HasClasses** | Academic calendar |

### Replace Sample Data

1. Edit `examples/daily_campus_forecast.py`
2. Load your CSV file:
   ```python
   df = load_historical_data('data/your_actual_data.csv')
   ```
3. Run the script

---

## 🌤️ Weather Integration

### OpenWeatherMap API (Recommended)

**Free tier:** 1000 calls/day

```python
import requests

API_KEY = "your_api_key"
lat, lon = 14.5995, 120.9842  # Your campus coordinates

url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
response = requests.get(url)
forecast = response.json()

for day in forecast['daily'][:7]:
    temp = day['temp']['day']
    humidity = day['humidity']
    rain = day.get('rain', 0)
```

**Get API key:** https://openweathermap.org/api

### Alternative Sources

- **PAGASA** - Philippine weather service (https://www.pagasa.dost.gov.ph/)
- **Campus Weather Station** - If available
- **Manual Input** - For testing

---

## 🔧 Backend API

### Start Daily Prediction API

```bash
cd backend
python daily_api.py
```

**API:** http://localhost:8000  
**Docs:** http://localhost:8000/docs

### Train Model

```python
import requests

data = {
    "consumption": [1450, 1520, 1480, ...],  # kWh per day
    "temperature": [28.5, 29.2, 27.8, ...],  # °C
    "humidity": [72, 68, 75, ...],           # %
    "rainfall": [0, 0, 5.2, ...],            # mm
    "has_classes": [1, 1, 1, ...],           # 1=yes, 0=no
    "day_of_week": [0, 1, 2, ...],           # 0=Mon, 6=Sun
    "is_weekend": [0, 0, 0, ...],            # 1=weekend, 0=weekday
    "epochs": 100
}

response = requests.post('http://localhost:8000/train-daily', json=data)
print(response.json())
```

### Get 7-Day Forecast

```python
forecast_request = {
    "past_data": {...},
    "future_weather": {...},
    "future_schedule": {...},
    "n_days": 7
}

response = requests.post('http://localhost:8000/forecast-daily', json=forecast_request)
result = response.json()

print(f"Total: {result['total_consumption']:.0f} kWh (₱{result['total_cost']:,.2f})")
```

---

## 💻 Technology Stack

### Backend
- **Python 3.8+**
- **TensorFlow 2.x** - Deep learning (LSTM)
- **scikit-learn** - Machine learning (SVM)
- **FastAPI** - REST API
- **NumPy** - Numerical computing
- **Pandas** - Data manipulation

### Frontend
- **HTML5/CSS3** - Structure and styling
- **JavaScript (ES6+)** - Interactivity
- **Chart.js** - Data visualization
- **Inter Font** - Typography

### AI Models
- **Enhanced LSTM** - Temporal pattern recognition with attention
- **SVM** - Non-linear relationship modeling
- **Hybrid Ensemble** - 70% LSTM + 30% SVM
- **Sequence Length** - 7 days
- **Input Features** - 8 (consumption, weather, schedule, temporal)

---

## 📈 Expected Performance

With 90+ days of quality data:

| Metric | Target | Excellent |
|--------|--------|-----------|
| **RMSE** | < 100 kWh | < 50 kWh |
| **MAE** | < 80 kWh | < 40 kWh |
| **MAPE** | < 8% | < 5% |
| **R²** | > 0.85 | > 0.92 |

---

## 🎯 Use Cases

### 1. Budget Planning

```
Predicted 7-day consumption: 10,500 kWh
Cost at ₱12.383/kWh: ₱130,021.50
+ 10% contingency: ₱13,002.15
Recommended budget: ₱143,023.65
```

### 2. Peak Load Management

```
Monday (class day, hot): 1,550 kWh → High load expected
Saturday (no class, rainy): 1,100 kWh → Low load expected
```

### 3. Energy Optimization

```
If temperature > 30°C and classes = yes:
  → Expect +200 kWh consumption
  → Pre-cool buildings before peak hours
  → Adjust AC schedules
```

### 4. Anomaly Detection

```
Predicted: 1,500 kWh
Actual: 2,100 kWh
Difference: +600 kWh (+40%)
→ Investigate: Equipment malfunction? Unusual event?
```

---

## 📚 Documentation

| Document | Purpose | Pages |
|----------|---------|-------|
| **`DAILY_PREDICTION_GUIDE.md`** | **Complete guide** | 15+ |
| **`START_HERE.md`** | **Quick start** | 5+ |
| `ARCHITECTURE.md` | System architecture | 12+ |
| `SYSTEM_STATUS.md` | Status report | 10+ |
| `QUICK_REFERENCE.md` | Quick reference | 2 |
| `COMPLETION_SUMMARY.md` | Completion summary | 8+ |
| `HOW_TO_USE_REAL_DATA.md` | Real data guide | 8+ |
| `CLEAN_SETUP.md` | Installation | 6+ |
| `FINAL_SYSTEM.md` | System docs | 8+ |

**Total:** 70+ pages of documentation

---

## 🔐 Authentication

### User Flow
1. User signs up → Status: Pending
2. Admin reviews and approves (password: `admin123`)
3. User can login and access dashboard

### Admin Panel
- View all users
- Approve/reject signups
- Revoke/restore access
- Access: `frontend/admin.html`

---

## 🌱 Green Design

The interface uses a green color scheme to emphasize:
- Energy conservation
- Sustainability
- Environmental responsibility
- Cost savings

---

## 🛠️ Customization

### Change Admin Password
Edit `frontend/admin.html`:
```javascript
const ADMIN_PASSWORD = 'your-new-password';
```

### Change Cost per kWh
Edit `frontend/dashboard.js`:
```javascript
const COST_PER_KWH = 12.383;  // Philippine Peso
```

### Modify Weather API
Edit `examples/daily_campus_forecast.py`:
```python
def get_weather_forecast(days=7):
    # Integrate your weather API here
    pass
```

---

## 🐛 Troubleshooting

**Low accuracy (MAPE > 15%)?**
- Collect more data (aim for 90+ days)
- Check data quality (missing values, outliers)
- Verify weather data accuracy
- Update class schedule information

**Backend not responding?**
- Check if server is running: http://localhost:8000/health
- Restart: `python backend/daily_api.py`

**Can't login after approval?**
- Refresh the login page
- Check admin panel for approval status

---

## 🎉 Ready to Use!

**Quick Start:**
1. Run `python examples/daily_campus_forecast.py`
2. See the predictions and understand the system
3. Collect your daily data (30+ days)
4. Replace sample data with your actual records
5. Generate accurate forecasts for your campus!

**Read `START_HERE.md` for complete instructions!** 📖

---

## 📝 License

This project is for educational and demonstration purposes.

---

## 📞 Support

For questions or issues:
- Read `DAILY_PREDICTION_GUIDE.md` for complete guide
- Check `START_HERE.md` for quick start
- Review `QUICK_REFERENCE.md` for commands
- API docs: http://localhost:8000/docs

---

**The system is designed to predict daily electricity consumption accurately using weather and schedule data. Start with the example and gradually integrate your real campus data!** 🎯✅
