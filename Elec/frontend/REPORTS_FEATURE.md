# Reports Feature - Real Interaction Tracking

## Overview
The reports page has been updated to track and display **real user interactions** instead of mockup data. All training, forecasting, and export activities on the dashboard are now automatically tracked and displayed on the reports page.

## Features Implemented

### 1. Real-Time Interaction Tracking
- **Training Events**: Every time you train a model (simple or daily), it's logged with:
  - Training type (simple/daily)
  - Number of data points used
  - Model performance metrics (RMSE, MAE, R², MAPE)
  - Timestamp

- **Forecast Events**: Every forecast generation is tracked with:
  - Forecast type (simple/daily)
  - Number of steps/days predicted
  - Total consumption and cost
  - Average consumption per step/day
  - Peak load analysis (for daily forecasts)
  - Timestamp

- **Export Events**: CSV exports are tracked with:
  - Export type
  - Number of data points exported
  - Timestamp

### 2. Recent Reports Section
- Displays last 5 interactions (training, forecasts, exports)
- Shows detailed metrics for each interaction
- Includes timestamp and report metadata
- Each report has a "Download PDF" button (placeholder for future implementation)
- Empty state message when no interactions exist yet

### 3. Report Templates
Six smart templates that generate reports based on current model data:
- **Daily Summary**: Daily consumption and forecast
- **Weekly Report**: Weekly trends and insights  
- **Monthly Analysis**: Monthly performance analysis
- **Cost Analysis**: Cost breakdown and savings
- **Building Comparison**: Compare building performance
- **Sustainability Report**: Environmental impact report

Each template button checks if model data is available before generating.

### 4. Scheduled Reports
- Displays configurable scheduled reports
- Shows frequency, recipients, next run time, and status
- Active/Paused status with toggle functionality
- Edit functionality for each scheduled report

## How It Works

### Data Flow
```
Dashboard (train/forecast) 
    → saveInteraction() 
    → localStorage 
    → Reports Page reads and displays
```

### Storage Keys
- `energyai.interactionHistory`: Stores last 50 interactions
- `energyai.scheduledReports`: Stores scheduled report configurations
- `energyai.shared.dailyModel`: Shared model data for report generation

### Interaction Types
1. **training**: Model training completion
2. **forecast**: Forecast generation completion
3. **report_generation**: Manual report generation
4. **export**: Data export to CSV
5. **download**: Report download

## Usage

### For Users
1. **Go to Dashboard**: Train a model and generate forecasts as usual
2. **Navigate to Reports**: Click "Reports" in the sidebar
3. **View Interactions**: See all your recent training and forecast activities
4. **Generate Reports**: Click template buttons or "Generate Report" to create reports
5. **Manage Schedules**: View and edit scheduled reports in the table

### For Developers

#### Track a New Interaction Type
```javascript
saveInteraction('new_type', {
    customField: 'value',
    timestamp: new Date().toISOString()
});
```

#### Read Interaction History
```javascript
const history = getInteractionHistory();
// Returns array of interaction objects
```

#### Add a New Report Template
Edit `renderReportTemplates()` in `reports.js`:
```javascript
{ 
    name: 'New Template', 
    icon: 'icon-name', 
    description: 'Description' 
}
```

## File Structure

### Modified Files
- `frontend/reports.html`: Updated to use external JS file
- `frontend/reports.js`: New file with all report logic
- `frontend/dashboard-fixed.js`: Added interaction tracking

### Key Functions

#### dashboard-fixed.js
- `saveInteraction(type, data)`: Saves interaction to localStorage

#### reports.js
- `getInteractionHistory()`: Retrieves all interactions
- `renderRecentReports()`: Displays recent interactions as report cards
- `renderReportTemplates()`: Displays clickable template buttons
- `renderScheduledReports()`: Displays scheduled reports table
- `generateReport(template)`: Generates report from template
- `openReportGenerator()`: Opens report generation dialog

## Future Enhancements

### Planned Features
1. **PDF Generation**: Convert interaction data to formatted PDF reports
2. **Email Scheduling**: Actually send scheduled reports via email
3. **Custom Templates**: Allow users to create custom report templates
4. **Advanced Filtering**: Filter interactions by date range, type, etc.
5. **Report Comparison**: Compare multiple reports side-by-side
6. **Export Options**: Export to Excel, CSV, JSON formats
7. **Charts in Reports**: Include visualizations in generated reports
8. **Report History**: View and manage all generated reports
9. **Report Sharing**: Share reports with team members
10. **Automated Insights**: AI-generated insights in reports

### Database Integration
For production, consider moving from localStorage to:
- Backend database (PostgreSQL, MongoDB)
- RESTful API for interaction tracking
- User authentication and multi-user support
- Report storage and versioning

## Testing

### Manual Testing Steps
1. **Open Dashboard**: Navigate to `dashboard.html`
2. **Train Model**: Use sample data and train a model
3. **Generate Forecast**: Create a forecast with the trained model
4. **Export Data**: Export forecast to CSV
5. **Check Reports**: Navigate to `reports.html`
6. **Verify Display**: Confirm all interactions appear in Recent Reports
7. **Test Templates**: Click template buttons to verify they work
8. **Test Download**: Click "Download PDF" buttons (shows alert for now)

### Automated Testing (Future)
```javascript
// Unit tests for interaction tracking
describe('Interaction Tracking', () => {
    it('should save training interaction', () => {
        saveInteraction('training', { dataPoints: 100 });
        const history = getInteractionHistory();
        expect(history[0].type).toBe('training');
    });
});
```

## Troubleshooting

### No Reports Showing
- Ensure you've trained a model on the dashboard first
- Check browser localStorage (DevTools → Application → Local Storage)
- Verify `energyai.interactionHistory` key exists

### Reports Not Updating
- Hard refresh the page (Ctrl+F5)
- Check for JavaScript errors in browser console
- Ensure reports.js is loaded correctly

### Model Data Not Available
- Train a model on the dashboard first
- Check `energyai.shared.dailyModel` in localStorage
- Verify model data has `trained: true` property

## Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- IE11: ❌ Not supported (uses modern JavaScript)

## Performance
- Interaction history limited to 50 entries to prevent localStorage bloat
- All rendering is client-side (no server requests)
- Minimal performance impact on dashboard operations

## Security Notes
- All data stored locally in browser
- No sensitive data transmitted over network
- Clear localStorage to remove all tracking data
- Consider encryption for sensitive deployments

---

**Version**: 1.0.0  
**Last Updated**: July 5, 2026  
**Author**: EnergyAI Development Team
