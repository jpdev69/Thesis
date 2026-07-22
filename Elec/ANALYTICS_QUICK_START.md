# Analytics Page - Quick Start Guide

## 🚀 Quick Test in 3 Minutes

### Step 1: View Initial State (No Data)
1. Open browser: `http://localhost:8080/analytics.html`
2. Login if prompted
3. **Expected State**:
   - Status badge shows: "No Model" (gray)
   - Summary text: "No trained model found. Train a model from the Dashboard... Today is July 5, 2026."
   - Charts show sample data for July 2026
   - Sample data includes weekday/weekend patterns

### Step 2: Train a Model
1. Navigate to **Dashboard** (click sidebar)
2. Click **"Sample Daily Data"** button
3. Click **"Train Model"** button
4. Wait 2-3 seconds for training to complete
5. **Expected**: Success message with metrics

### Step 3: View Updated Analytics
1. Return to **Analytics** page (click sidebar)
2. **Expected Changes**:
   - Status badge: "1 Activities" (green)
   - Summary: "Analytics based on 1 training session..."
   - Real metrics: "RMSE 45.2 kWh, MAE 38.7 kWh, R² 0.890"
   - Date reference: "Data as of July 5, 2026"
   - Stat changes updated with real comparisons

### Step 4: Generate a Forecast
1. Go back to **Dashboard**
2. Click **"Generate Daily Forecast"** (default 7 days)
3. Wait for forecast completion
4. **Expected**: Chart updates with predictions

### Step 5: Check Analytics Again
1. Return to **Analytics** page
2. **Expected Changes**:
   - Status badge: "2 Activities" (green)
   - Summary: "...1 training session and 1 forecast"
   - Projected Savings: Updated from forecast data
   - Facilities stat: "2 activities today"

## 🎯 What to Expect

### ✅ Success Indicators
- Dates consistently show July 2026
- Status badge updates with activity count
- Summary text includes training/forecast counts
- Real metrics appear after model training
- Stat changes reflect actual data comparisons
- Charts update with real consumption data

### 📊 Sample Data Patterns

When no real data exists, you'll see:
- **Weekday consumption**: ~3200 kWh
- **Weekend consumption**: ~2400 kWh (75% of weekday)
- **Variations**: ±15% random fluctuation
- **Date range**: Last 30 days from July 5, 2026

## 🔍 Inspect the Data

### View Analytics State
```javascript
// Open browser console (F12)

// Check interaction history
JSON.parse(localStorage.getItem('energyai.interactionHistory'))

// Check model data
JSON.parse(localStorage.getItem('energyai.shared.dailyModel'))

// Check current date
new Date('2026-07-05').toLocaleDateString()
// Output: "7/5/2026"
```

### Verify Date Consistency
All these should reference July 2026:
- Default chart labels
- Summary text date
- Sample data generation
- Stat change calculations

## 📈 Test Each Feature

### 1. Period Selector
1. Click period dropdown (top right)
2. Select "Last 30 Days"
3. **Expected**: Trend chart shows 30 days
4. Select "Last 7 Days"
5. **Expected**: Trend chart shows 7 days

### 2. Chart Controls
1. Click "Weekly" button on Usage Trends chart
2. **Expected**: Chart aggregates into weeks
3. Click "Monthly" button
4. **Expected**: Chart aggregates into months
5. Click "Daily" button
6. **Expected**: Chart returns to daily view

### 3. Theme Toggle
1. Click sun/moon icon (top right)
2. **Expected**: Theme switches dark/light
3. Charts update colors automatically
4. Refresh page
5. **Expected**: Theme persists

### 4. Cross-Tab Sync
1. Open Analytics in Tab 1
2. Open Dashboard in Tab 2
3. Train model in Tab 2
4. Switch to Tab 1 (Analytics)
5. **Expected**: Stats auto-update within 1 second

## 🧪 Advanced Testing

### Test Multiple Training Sessions
1. Train model (session 1)
2. Check Analytics: "1 training session"
3. Return to Dashboard
4. Train model again (session 2)
5. Check Analytics: "2 training sessions"
6. **Expected**: Activity count increments

### Test Consumption Comparison
1. Train model with sample data
2. Note the "Estimated Consumption" value
3. Note the "vs last period" percentage
4. **Expected**: Percentage calculated from actual data

### Test Real Peak Demand
1. Train model with varying consumption data
2. Check "Peak Demand Outlook" stat
3. **Expected**: Peak scales with your data
4. **Formula**: `Math.max(latest * 0.12, 80)`

### Test Facilities Count
1. Train with different data sizes
2. **Expected**: Facilities count changes
3. **Formula**: `Math.ceil(dataPoints / 2.5)`
4. More data points = more facilities

## 📋 Verification Checklist

### Visual Elements
- [ ] Status badge displays correctly
- [ ] Status badge color is appropriate (gray/blue/green)
- [ ] All dates reference July 2026
- [ ] Summary text is informative
- [ ] Stat cards show realistic values
- [ ] Stat changes have proper +/- indicators
- [ ] Charts render without errors
- [ ] Building names are realistic

### Data Integration
- [ ] localStorage has `interactionHistory` key
- [ ] Status badge updates with activity count
- [ ] Summary shows training/forecast counts
- [ ] Real metrics appear after training
- [ ] Savings calculation uses forecast data
- [ ] Consumption shows real data patterns

### Interactivity
- [ ] Period selector changes chart range
- [ ] Chart control buttons work (Daily/Weekly/Monthly)
- [ ] Theme toggle persists across refreshes
- [ ] Cross-tab updates work automatically
- [ ] No JavaScript errors in console

### Dates & Time
- [ ] Default dates start from July 5, 2026
- [ ] Sample data covers last 30 days
- [ ] Current date appears in summary
- [ ] Weekend pattern visible in sample data
- [ ] Peak hour shows realistic time (12-4 PM)

## ❌ Troubleshooting

### Issue: Status badge shows "No Model" after training
**Cause**: localStorage not updated  
**Fix**:
1. Check browser console for errors
2. Verify training completed successfully
3. Check localStorage: `localStorage.getItem('energyai.interactionHistory')`
4. Try hard refresh: Ctrl+F5

### Issue: Dates showing current system time instead of July 2026
**Cause**: Old cached JavaScript  
**Fix**:
1. Hard refresh page (Ctrl+F5)
2. Clear browser cache
3. Verify script version: `analytics.js?v=20260705b`

### Issue: Charts not updating with real data
**Cause**: Model data not available  
**Fix**:
1. Train model on dashboard first
2. Check localStorage: `localStorage.getItem('energyai.shared.dailyModel')`
3. Ensure model has `trained: true`
4. Refresh analytics page

### Issue: "NaN" or "undefined" in stats
**Cause**: Missing data fields  
**Fix**:
1. Use latest dashboard-fixed.js version
2. Clear localStorage: `localStorage.clear()`
3. Train a fresh model
4. Verify interaction data structure

### Issue: Cross-tab sync not working
**Cause**: Storage events not firing  
**Fix**:
1. Ensure both tabs are from same origin
2. Check browser console for errors
3. Verify localStorage is enabled
4. Try incognito/private browsing mode

## 💡 Pro Tips

### 1. Test with Real Patterns
```javascript
// Generate realistic campus data
const workdays = 20; // 20 workdays
const weekends = 10; // 10 weekend days
const workdayLoad = 3200;
const weekendLoad = 2400;
// Mix in your training data
```

### 2. Monitor Storage Size
```javascript
// Check localStorage usage
const used = JSON.stringify(localStorage).length;
console.log(`Storage used: ${(used/1024).toFixed(2)} KB`);
```

### 3. Debug Mode
```javascript
// Enable verbose logging
localStorage.setItem('debug', 'true');
// Check console for detailed logs
```

### 4. Reset Everything
```javascript
// Clear all EnergyAI data
localStorage.removeItem('energyai.interactionHistory');
localStorage.removeItem('energyai.shared.dailyModel');
localStorage.removeItem('energyai.scheduledReports');
// Refresh page for clean state
```

### 5. Export Analytics Data
```javascript
// Get all analytics data
const data = {
    interactions: JSON.parse(localStorage.getItem('energyai.interactionHistory')),
    model: JSON.parse(localStorage.getItem('energyai.shared.dailyModel')),
    timestamp: new Date().toISOString()
};
console.log(JSON.stringify(data, null, 2));
// Copy from console to save
```

## 🎨 Customization Tips

### Change Sample Data Pattern
In `analytics.js`, modify `defaultConsumption()`:
```javascript
const baseLoad = 3200; // Change base load
const weekendFactor = 0.75; // Change weekend reduction
const randomVariation = 0.85 + Math.random() * 0.3; // Adjust variation
```

### Change Current Date
In `analytics.js`, modify `getCurrentDateInfo()`:
```javascript
today: new Date('2026-07-05'), // Change to any date
```

### Change Building Names
In `analytics.js`, modify `initCharts()`:
```javascript
labels: ['Main Campus', 'Library', 'Gymnasium', 'Lab Building', 'Admin Office']
// Change to your facility names
```

### Adjust Savings Percentage
In `analytics.js`, modify savings calculation:
```javascript
savingsEstimate = forecastData.totalCost * 0.065; // Change 0.065 to desired %
```

## 📚 Related Documentation

- `ANALYTICS_UPDATE_SUMMARY.md` - Complete change log
- `REPORTS_UPDATE_SUMMARY.md` - Reports page changes
- `REPORTS_QUICK_START.md` - Reports testing guide
- `REPORTS_ARCHITECTURE.md` - System architecture

## 🔗 Integration Points

### With Dashboard
- Receives training interactions
- Receives forecast interactions
- Shares model data via localStorage
- Auto-updates on dashboard activity

### With Reports
- Shares interaction history
- Common data format
- Cross-page consistency
- Unified activity tracking

## 🎉 Success Criteria

You've successfully tested the analytics page when:

✅ Status badge shows activity count after training  
✅ Dates consistently reference July 2026  
✅ Real metrics appear in summary text  
✅ Stat changes calculate from actual data  
✅ Charts update with real consumption patterns  
✅ Cross-tab synchronization works  
✅ No console errors present  
✅ Theme toggle persists  
✅ Period selector changes chart range  
✅ Chart controls aggregate data correctly  

---

**Testing Time**: ~3 minutes  
**Last Updated**: July 5, 2026  
**Version**: 1.0.0
