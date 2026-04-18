---
name: evaluation
description: Model evaluation — metrics, error analysis, fairness, calibration, and comparison
category: ds_methodology
tags: [evaluation, metrics, error-analysis, fairness, calibration, shap]
version: "1.0.0"
author: builtin
token_estimate: 1100
related_skills: [modeling, reporting]
---

# Model Evaluation

## When to Use This Skill
- After model training is complete
- Before deciding on a final model
- When assessing model readiness for deployment

## Step-by-Step Procedure

### 1. Metric Computation (on TEST set only)
- **Classification**: accuracy, precision, recall, F1, AUC-ROC, log loss
- **Regression**: RMSE, MAE, MAPE, R², explained variance
- Compare against baseline — must show meaningful improvement

### 2. Error Analysis
- Identify worst predictions (highest error / most confident misclassifications)
- Look for patterns: are errors concentrated in a subgroup?
- Confusion matrix analysis (classification)
- Residual analysis (regression): plot residuals vs predicted, residuals vs features

### 3. Feature Importance
- **SHAP values**: global and local explanations (preferred)
- **Permutation importance**: model-agnostic
- **Built-in importance**: tree-based models (gain, split count)
- Visualize: SHAP summary plot, top-N features bar chart

### 4. Segment Analysis
- Evaluate performance across meaningful segments
- Examples: by region, by customer type, by time period
- Identify segments where model underperforms

### 5. Calibration Analysis (Classification)
- Plot calibration curve (predicted probability vs actual frequency)
- Calculate Brier score
- Apply calibration if needed (Platt scaling, isotonic regression)

### 6. Fairness Audit (if applicable)
- Check metrics across protected groups (gender, age, race)
- Demographic parity: are positive rates similar across groups?
- Equal opportunity: are true positive rates similar?
- Document any disparities

### 7. Model Comparison Summary
- Create comparison table: all models, all metrics
- Consider: performance, training time, inference speed, interpretability
- Recommend final model with justification

## Common Pitfalls
- Evaluating on training data (always use held-out test set)
- Only reporting accuracy on imbalanced datasets
- Ignoring calibration for probability-based decisions
- Not doing error analysis (just looking at aggregate metrics)

## Quality Checks
- [ ] Evaluated on held-out test data only
- [ ] Multiple metrics reported (not just one)
- [ ] Error analysis completed
- [ ] Feature importance computed
- [ ] Model beats baseline by meaningful margin
- [ ] Fairness checked if applicable

## Output Expectations
- Evaluation report with metrics table
- SHAP plots saved as artifacts
- Confusion matrix / residual plots
- Model comparison table
