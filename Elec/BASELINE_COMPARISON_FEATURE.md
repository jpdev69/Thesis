# Baseline Comparison Feature - Complete Documentation

## Overview
The baseline comparison feature in the Technical Model Catalog provides a comprehensive performance evaluation by comparing the trained ML model against three simple baseline methods. This validates that the model's complexity is justified by meaningful performance improvements.

## What Changed

### ✅ Completed Tasks
1. **Removed standalone "Baseline Comparison" card section** with individual model cards
2. **Removed "Operations History" card** (irrelevant to model evaluation)
3. **Integrated baseline comparison directly into Technical Model Catalog table**
4. **Added improvement percentage for all models** including the current ML model

### Technical Model Catalog Structure
The table now displays all models in a single, unified view:

| Model Name | Type | RMSE | MAE | R² Score | Improvement | Status |
|------------|------|------|-----|----------|-------------|--------|
| Daily Predictor | ML Model | X.XX | X.XX | 0.XXX | +XX.X% | Active |
| Linear Regression | Baseline | X.XX | X.XX | 0.XXX | +XX.X% | Reference |
| Persistence (Naive) | Baseline | X.XX | X.XX | 0.XXX | +XX.X% | Reference |
| Historical Mean | Baseline | X.XX | X.XX | 0.XXX | +XX.X% | Reference |

## Baseline Methods Explained

### 1. Persistence (Naive)
- **Method**: Predicts tomorrow's value = today's value
- **Use Case**: Simplest possible forecast; good for stable, slowly-changing data
- **Formula**: `prediction(t+1) = actual(t)`

### 2. Historical Mean
- **Method**: Always predicts the historical average
- **Use Case**: Captures overall level but ignores trends and patterns
- **Formula**: `prediction = mean(historical_data)`

### 3. Linear Regression
- **Method**: Simple linear trend model
- **Use Case**: Captures basic upward/downward trends
- **Formula**: `prediction = intercept + slope × time_index`

### 4. Daily Predictor (Current ML Model)
- **Method**: Multi-factor regression with weather and schedule features
- **Features Used**: Temperature, humidity, rainfall, class schedule
- **Use Case**: Complex patterns with multiple influencing factors

## Performance Metrics

### RMSE (Root Mean Square Error)
- **What it measures**: Average prediction error magnitude
- **Units**: Same as target (kWh)
- **Better value**: Lower is better
- **Typical target**: < 5 kWh for daily campus consumption

### MAE (Mean Absolute Error)
- **What it measures**: Average absolute prediction error
- **Units**: Same as target (kWh)
- **Better value**: Lower is better
- **Typical target**: < 4 kWh

### R² Score (Coefficient of Determination)
- **What it measures**: Proportion of variance explained by the model
- **Range**: 0 to 1 (can be negative for very poor models)
- **Better value**: Higher is better (1 = perfect fit)
- **Typical target**: > 0.90 for good predictive models

### Improvement Percentage
- **Calculation**: `(baseline_RMSE - current_RMSE) / baseline_RMSE × 100`
- **Interpretation**: 
  - **Current ML Model**: Improvement vs **best baseline** (lowest RMSE among the 3 baselines)
  - **Baseline Models**: How much worse they are compared to current model
- **Example**: +35.2% means current model reduces error by 35.2% compared to best simple method

## Dynamic Catalog Features

### Automatic Sorting
- Models are sorted by R² score (best performance first)
- Current model highlighted with green background and Active badge
- Baseline models marked as Reference

### Performance Badge
Shows overall model quality at catalog header:
- **Excellent (+30%+)**: Green badge - significant improvement over baselines
- **Good (+10-30%)**: Yellow badge - moderate improvement
- **Modest (<10%)**: Gray badge - minimal improvement, consider simpler approaches

### Performance Insight Box
Appears below the table with context-aware analysis:
- **Excellent Performance**: >30% improvement - complexity well-justified
- **Good Performance**: 10-30% improvement - reasonable gains
- **Modest Performance**: 0-10% improvement - consider if complexity worth it
- **Performance Warning**: Negative improvement - model may be overfitting or poorly configured

## How It Works

### 1. Model Training
When you train a model on `/models.html`:
```javascript
trainTechnicalModel()
  ↓
DailyPredictor.train(data)
  ↓
Calculates metrics on holdout validation set (20% of data)
  ↓
Saves model + metrics to localStorage
  ↓
Updates evaluation metrics display
```

### 2. Baseline Calculation
```javascript
updateModelCatalog(currentMetrics)
  ↓
calculateBaselineMetrics(historicalData)
  ↓
For each baseline method:
  - Make predictions on training data
  - Calculate RMSE, MAE, R² vs actual values
  ↓
Compare current model vs all baselines
  ↓
Update table with sorted results
```

### 3. Improvement Calculation
```javascript
// For current ML model
bestBaselineRMSE = min(persistence.RMSE, mean.RMSE, linear.RMSE)
improvement = (bestBaselineRMSE - currentRMSE) / bestBaselineRMSE × 100

// For baseline models
improvement = (baseline.RMSE - currentRMSE) / baseline.RMSE × 100
```

## File Structure

### Modified Files
- **`frontend/models.html`**: 
  - Removed separate baseline comparison card
  - Removed operations history card
  - Enhanced model catalog table with baseline integration
  - Added `calculateBaselineMetrics()` function
  - Added `updateModelCatalog()` function with improvement for current model

### Key Functions

#### `calculateBaselineMetrics(historicalData)`
- **Purpose**: Compute RMSE, MAE, R² for all baseline methods
- **Input**: Historical consumption data array
- **Output**: Object with metrics for persistence, mean, and linear baselines
- **Location**: `models.html` script section

#### `updateModelCatalog(currentMetrics)`
- **Purpose**: Update catalog table with current model + baseline comparison
- **Input**: Current model's training metrics (RMSE, MAE, R²)
- **Process**:
  1. Load historical data from localStorage
  2. Calculate baseline metrics
  3. Compute improvements for all models
  4. Sort by R² score
  5. Generate table HTML
  6. Update badge and insight box
- **Location**: `models.html` script section

#### `updateEvaluationMetrics(metrics)`
- **Purpose**: Display metrics and trigger catalog update
- **Side Effect**: Calls `updateModelCatalog(metrics)` to refresh table
- **Location**: `models.html` script section

## Usage Instructions

### For Technical Staff
1. Navigate to `/models.html`
2. Provide training data (CSV with Date, Consumption, Temperature, Humidity, Rainfall, HasClasses)
3. Click "Train Model"
4. View updated Technical Model Catalog with:
   - Current model performance
   - Baseline comparisons
   - Performance badge
   - Insight analysis

### Interpreting Results

#### High Improvement (>30%)
✅ **Model is valuable** - complexity justified by significant gains
- Continue using ML approach
- Monitor performance on new data
- Consider deploying to production

#### Moderate Improvement (10-30%)
⚠️ **Model is useful** - provides reasonable benefit
- Acceptable for most applications
- May benefit from feature engineering or hyperparameter tuning
- Compare cost of complexity vs value of improvement

#### Low Improvement (<10%)
🔍 **Reassess approach** - gains may not justify complexity
- Consider using simpler baseline (Linear Regression)
- Check for data quality issues
- Verify features are informative
- May indicate data lacks predictable patterns

#### Negative Improvement
❌ **Model has issues** - performing worse than baselines
- Likely overfitting on training data
- May need more training data
- Review feature selection
- Check for data leakage or bugs

## Best Practices

### When to Trust the Comparison
✅ Training data size: >30 days minimum
✅ Holdout validation: 20% held out for testing
✅ Data quality: Clean, complete records
✅ Feature relevance: Weather and schedule actually influence consumption

### When to Be Cautious
⚠️ Small datasets (<14 days)
⚠️ Missing or sparse data
⚠️ Highly irregular patterns (outliers, anomalies)
⚠️ External factors not captured in features

### Recommended Actions by Performance Level

**Excellent (>30% improvement)**
- Deploy model with confidence
- Monitor performance metrics regularly
- Set up automated retraining schedule
- Document deployment for stakeholders

**Good (10-30% improvement)**
- Deploy with monitoring
- Consider feature improvements
- Track performance vs baselines over time
- Plan periodic model updates

**Modest (<10% improvement)**
- Evaluate if complexity worth it
- Test simpler approaches (e.g., Linear Regression)
- Investigate feature engineering opportunities
- May use baseline for simplicity

**Poor (negative improvement)**
- Do not deploy
- Investigate root causes
- Collect more/better data
- Revisit problem formulation
- Use best baseline temporarily

## Future Enhancements

### Potential Additions
1. **Time-based cross-validation**: Multiple train/test splits for robustness
2. **Confidence intervals**: Show uncertainty in improvement estimates
3. **Baseline ensemble**: Combine multiple baselines for stronger comparison
4. **Feature importance**: Show which features drive ML model improvement
5. **Cost-benefit analysis**: Compare computational cost vs accuracy gain

### Requested Features
- Export comparison table to CSV/PDF
- Historical tracking of model improvements over time
- A/B testing framework for model comparison
- Alert system when performance drops below baseline

## Technical Notes

### Why Compare RMSE for Improvement?
- RMSE penalizes large errors more heavily (squared term)
- More sensitive to outliers and extreme mispredictions
- Standard metric in forecasting literature
- Directly comparable across models

### Why Not Use R² for Improvement?
- R² can be misleading when comparing different model types
- Baseline models may have very low or negative R²
- RMSE improvement percentage is more intuitive

### Calculation Edge Cases
- If baseline RMSE = 0 (perfect baseline): improvement set to 0%
- If current RMSE > baseline RMSE: negative improvement shown (red)
- If historical data insufficient (<2 points): catalog shows placeholder

## Summary

The integrated baseline comparison in the Technical Model Catalog provides:
✅ **Single unified view** of all models and baselines
✅ **Clear improvement metrics** including for the current ML model
✅ **Automatic performance assessment** with badges and insights
✅ **Evidence-based decision making** for model deployment
✅ **Validation of model complexity** through comparative analysis

This feature ensures that stakeholders can objectively evaluate whether the ML model provides meaningful value over simpler alternatives, supporting informed decisions about model deployment and resource allocation.

---

**Last Updated**: July 5, 2026
**Component**: Technical Model Catalog
**Location**: `/models.html`
