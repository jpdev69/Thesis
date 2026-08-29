# Thesis Objective Outline (Final)

Use this file as the final objective-to-evidence map for defense.
Detailed results: `docs/OBJECTIVES_AND_RESULTS_STATUS.md`.
Plain-language explanation of evaluation protocols:
`docs/EVALUATION_PROTOCOLS_AND_FINDINGS_EXPLAINED.md`.
Frozen configuration: `docs/final_training_configuration.md`.

## Objective 1: Build cascaded hybrid LSTM-SVM forecasting model

- Requirement: Attention-enhanced LSTM as temporal feature extractor and
  SVM as final regressor, cascaded (not weighted averaging).
- Evidence:
  - Real TensorFlow training on 943 real-derived daily records
    (794 sequences, 16 features per timestep).
  - `src/models/daily_prediction_model.py`, `src/models/hybrid_model.py`
  - Runner: `examples/train_daily_canonical.py`
- Status: Completed (3 latent model bugs fixed to enable real training).

## Objective 2: Compare with traditional baseline (ARIMA)

- Requirement: empirical comparison against ARIMA under aligned evaluation.
- Evidence:
  - 142-day recursive stress test: hybrid wins all four core metrics
    (RMSE -26.0%, MAPE 18.15% vs 21.08%).
  - Rolling 7-day: ARIMA wins the headline (11.79% vs 14.92% MAPE);
    hybrid wins shape accuracy (5.71% vs 6.74% level-corrected) and
    directional accuracy (60.4% vs 44.6%).
  - Root cause of headline gap decomposed and documented
    (monthly billing-anchor level bias; not staleness — retraining
    variant confirmed).
  - Files: `data/processed/hybrid_vs_arima_test_metrics.csv`,
    `data/processed/rolling_7day*_metrics.csv`,
    `docs/rolling_7day_evaluation_report.md`,
    `docs/rolling_7day_expanding_report.md`
- Status: Completed.

## Objective 3: Evaluate weather variable contribution

- Requirement: include meteorological variables and quantify
  forecasting quality.
- Evidence:
  - Ablation: weather alone improves MAPE 6.71% -> 5.81% and
    R2 0.8101 -> 0.8869 versus consumption-only baseline.
  - Files: `docs/ablation_study_report.md`,
    `data/processed/ablation_results.csv`
- Status: Completed.

## Objective 4: Apply schedule awareness and prescriptive advisories

- Requirement: include class/weekend/holiday context and map outputs to
  actions/cost-aware guidance.
- Evidence:
  - Ablation: schedule alone improves MAPE 6.71% -> 5.27%.
  - 34 anomalous days flagged; 7-day sample forecast with confidence
    intervals and schedule-aware structure
    (`data/processed/7day_recursive_forecast_samples.csv`).
  - Advisory/cost flows in `backend/daily_api.py` and frontend.
- Status: Completed.

## Objective 5: Validate rolling 7-day performance targets

- Requirement: recursive 7-day look-ahead, reported RMSE, MAE, MAPE, R2.
- Evidence:
  - Full rolling-origin protocol executed twice (frozen and
    retrained-per-origin hybrids, 20 weekly windows each).
  - Headline: hybrid MAPE 14.92%, R2 0.11 — targets NOT met.
  - Shape-decomposed: MAPE 5.71% — target met.
  - Short-horizon validation: MAPE ~6.3%, R2 ~0.87 — targets met.
  - Root cause documented: month-level billing-anchor bias
    (meter-coverage changes, monthly-bill reconstruction), proven
    structural by the retraining experiment.
  - Files: `docs/rolling_7day_evaluation_report.md`,
    `docs/rolling_7day_expanding_report.md`
- Status: Evaluation completed; targets met on shape and validation
  regimes, not on the rolling headline; limitation declared.

## Final Defense Evidence Pack

1. Architecture and pipeline mapping (`ARCHITECTURE.md`)
2. Canonical daily dataset + QA report
   (`data/daily_canonical_dataset.csv`, `docs/daily_data_quality_report.md`)
3. Frozen training configuration (`docs/final_training_configuration.md`)
4. Hybrid vs ARIMA metric tables (stress test + rolling 7-day, both
   variants) and benchmark outputs
5. 7-day forecast samples with cost translation
6. Ablation results (weather and schedule contribution)
7. Shape/level decomposition and declared data limitations
8. Objective-to-evidence map and results status
   (`docs/OBJECTIVES_AND_RESULTS_STATUS.md`)
9. Evaluation protocols explained
   (`docs/EVALUATION_PROTOCOLS_AND_FINDINGS_EXPLAINED.md`)
