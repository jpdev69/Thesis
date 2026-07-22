# Reports Feature - Quick Start Guide

## 🚀 Quick Test in 5 Minutes

### Step 1: Open the Dashboard
1. Start your local server (if not already running)
2. Open browser and navigate to `http://localhost:8080/dashboard.html`
3. Login if prompted (use your existing credentials)

### Step 2: Train a Model
1. Look for the **"Sample Daily Data"** button (green button in the data input section)
2. Click it to load sample data (30 days of energy consumption with weather data)
3. Click the **"Train Model"** button
4. Wait ~2-3 seconds for training to complete
5. You should see success messages in the status log showing metrics like:
   ```
   Daily prediction model trained successfully!
   Real metrics — RMSE: 45.20, MAE: 38.70, MAPE: 5.20%, R²: 0.89
   ```

### Step 3: Generate a Forecast
1. After training, click the **"Generate Daily Forecast"** button
2. The default forecast is for 7 days
3. Wait ~1-2 seconds for the forecast to complete
4. You should see:
   - A chart with predictions
   - Cost estimates
   - Confidence intervals
   - Success messages in the log

### Step 4: View Reports
1. Click **"Reports"** in the left sidebar
2. You should now see:
   - **Recent Reports** section showing your training and forecast activities
   - Each report card displays:
     - Report title (e.g., "Model Training Report - July 2026")
     - Generated timestamp
     - Key metrics (RMSE, R², data points, consumption, costs)
     - "Download PDF" button

### Step 5: Test Report Templates
1. Scroll to the **"Report Templates"** section on the right
2. Click any template button (e.g., "Daily Summary")
3. A dialog will show confirming report generation
4. The interaction is tracked and will appear in Recent Reports

### Step 6: Test Scheduled Reports
1. Scroll to the **"Scheduled Reports"** table
2. Click **"Pause"** on any active report
3. The status should change from "Active" to "Paused"
4. Click **"Resume"** to reactivate it

## 🎯 What to Expect

### ✅ Success Indicators
- Recent Reports shows 2+ entries (training + forecast)
- Each report has accurate timestamps
- Metrics match what you saw on the dashboard
- Template buttons check for model data before generating
- Scheduled reports table displays and updates correctly

### ❌ If Something's Wrong

#### No Reports Showing?
**Problem**: "No reports generated yet" message appears  
**Solution**: 
1. Go back to dashboard
2. Ensure you trained a model (look for success message)
3. Ensure you generated a forecast
4. Return to reports page and refresh (F5)

#### Reports Not Updating?
**Problem**: New training/forecast not appearing  
**Solution**:
1. Hard refresh the page (Ctrl + F5 or Cmd + Shift + R)
2. Check browser console (F12) for errors
3. Verify localStorage:
   - Open DevTools (F12)
   - Go to Application → Local Storage
   - Find `energyai.interactionHistory`
   - Should see JSON array with your interactions

#### "No trained model available" Error?
**Problem**: Template buttons show this error  
**Solution**:
1. Train a model on the dashboard first
2. Check localStorage for `energyai.shared.dailyModel`
3. Verify it has `trained: true` property

## 🔍 Inspect the Data

### View Interaction History
1. Open browser DevTools (F12)
2. Go to Console tab
3. Type: `JSON.parse(localStorage.getItem('energyai.interactionHistory'))`
4. Press Enter
5. You'll see array of all interactions with full details

### View Shared Model Data
1. In Console, type: `JSON.parse(localStorage.getItem('energyai.shared.dailyModel'))`
2. Press Enter
3. You'll see current model state with training metrics

## 📊 Sample Expected Output

### After Training
```javascript
{
    id: 1720051200000,
    type: "training",
    timestamp: "2026-07-05T10:30:00.000Z",
    data: {
        type: "daily",
        dataPoints: 30,
        metrics: {
            RMSE: 45.2,
            MAE: 38.7,
            MAPE: 5.2,
            R2: 0.89
        },
        classDays: 20,
        noClassDays: 10
    }
}
```

### After Forecasting
```javascript
{
    id: 1720051260000,
    type: "forecast",
    timestamp: "2026-07-05T10:31:00.000Z",
    data: {
        type: "daily",
        days: 7,
        totalConsumption: 1050.5,
        totalCost: 13005.23,
        avgDaily: 150.07,
        peakLoad: 175.3,
        loadFactor: 0.856
    }
}
```

## 🧪 Advanced Testing

### Test Multiple Forecasts
1. Generate a 7-day forecast
2. Check Reports → see new entry
3. Generate a 14-day forecast  
4. Check Reports → see both entries
5. Verify they're sorted by timestamp (newest first)

### Test Export Tracking
1. On Dashboard, generate a forecast
2. Click **"Export CSV"** button
3. Go to Reports page
4. You should see an export entry in the history

### Test Cross-Tab Updates
1. Open Dashboard in Tab 1
2. Open Reports in Tab 2
3. Train a model in Tab 1
4. Switch to Tab 2 (Reports)
5. The new training should auto-appear (via storage event)

### Test Theme Persistence
1. Toggle theme (sun/moon icon in header)
2. Refresh the page
3. Theme should remain the same

## 📝 Manual Verification Checklist

- [ ] Dashboard loads without errors
- [ ] Sample data can be loaded
- [ ] Model training completes successfully
- [ ] Forecast generation works
- [ ] Reports page displays
- [ ] Recent Reports shows training activity
- [ ] Recent Reports shows forecast activity
- [ ] Report details include metrics
- [ ] Timestamps are accurate
- [ ] Download buttons are present
- [ ] Template buttons work
- [ ] Template buttons check for model data
- [ ] Scheduled reports table displays
- [ ] Scheduled reports can be toggled
- [ ] Theme toggle works
- [ ] Page subtitle shows model info
- [ ] localStorage contains interaction data
- [ ] No JavaScript errors in console

## 🐛 Common Issues and Fixes

### Issue: localStorage Quota Exceeded
**Symptom**: "QuotaExceededError" in console  
**Fix**: 
```javascript
// Clear old data
localStorage.removeItem('energyai.interactionHistory');
// Try again
```

### Issue: Old Mockup Data Still Showing
**Symptom**: Seeing "January 2025" reports  
**Fix**: Hard refresh (Ctrl + F5) - the new code should override

### Issue: JSON Parse Error
**Symptom**: "Unexpected token" error in console  
**Fix**:
```javascript
// Clear corrupted data
localStorage.removeItem('energyai.interactionHistory');
localStorage.removeItem('energyai.scheduledReports');
// Refresh page
```

### Issue: Metrics Not Showing Correctly
**Symptom**: "undefined" or "NaN" in report details  
**Fix**: Ensure you're using the updated dashboard-fixed.js that tracks metrics

## 🎨 Customization Quick Tips

### Change Number of Visible Reports
In `reports.js`, line ~175:
```javascript
const reportsToShow = reportableInteractions.slice(0, 5); // Change 5 to desired number
```

### Change History Limit
In `reports.js`, line ~30:
```javascript
if (history.length > 50) { // Change 50 to desired limit
    history.splice(50);
}
```

### Add New Report Template
In `reports.js`, line ~190, add to templates array:
```javascript
{ 
    name: 'Custom Report', 
    icon: 'icon-name', 
    description: 'Your description' 
}
```

## 📚 Next Steps

### Learn More
- Read `REPORTS_FEATURE.md` for complete documentation
- Check `REPORTS_ARCHITECTURE.md` for technical details
- Review `REPORTS_UPDATE_SUMMARY.md` for what changed

### Implement PDF Generation
1. Install a PDF library (e.g., jsPDF)
2. Create PDF template
3. Update `downloadReport()` function in `reports.js`
4. Generate and download actual PDFs

### Add Backend Integration
1. Create API endpoint for interaction tracking
2. Store in database instead of localStorage
3. Add user authentication
4. Enable multi-user support

## 💡 Pro Tips

1. **Use Multiple Browser Tabs**: Open dashboard and reports in separate tabs to see real-time updates

2. **Check Network Tab**: Open DevTools → Network to monitor API calls (if backend integrated)

3. **Use Console Logging**: Uncomment console.log statements in code for debugging

4. **Bookmark Test Data**: Save good test datasets for quick testing

5. **Test Edge Cases**: Try with 0 data points, 1000+ points, invalid data

## 🎉 Success!

If you can see your training and forecast activities in the Reports page, congratulations! The real interaction tracking is working perfectly.

---

**Need Help?**
- Check browser console for errors (F12)
- Review localStorage data structure
- Ensure you're using the latest code versions
- Try clearing cache and localStorage if issues persist

**Document Version**: 1.0.0  
**Last Updated**: July 5, 2026
