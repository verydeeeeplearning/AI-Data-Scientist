---
name: modeling
description: Model training strategy — baseline, algorithm selection, cross-validation, hyperparameter tuning
category: ds_methodology
tags: [modeling, training, cross-validation, hyperparameter, baseline, ensemble]
version: "1.0.0"
author: builtin
token_estimate: 1300
related_skills: [feature-engineering, evaluation]
---

# Modeling

## When to Use This Skill
- After feature engineering is complete
- When training models on prepared feature matrices
- When optimizing model performance

## Step-by-Step Procedure

### 1. Establish Baselines
**ALWAYS start with simple baselines before complex models.**
- **Classification**: majority class, random, logistic regression
- **Regression**: mean prediction, linear regression
- **Time Series**: naive forecast (last value), seasonal naive
- Record baseline metrics — everything else must beat this

### 2. Algorithm Selection Guide

| Data Characteristics | Recommended Models |
|---------------------|-------------------|
| Small data (<1K rows) | Logistic/Linear Regression, SVM, KNN |
| Medium data (1K-100K) | Random Forest, XGBoost, LightGBM |
| Large data (>100K) | LightGBM, CatBoost, Neural Nets |
| High cardinality categoricals | CatBoost, LightGBM |
| Interpretability required | Logistic Regression, Decision Tree, EBM |
| Tabular data (general) | LightGBM > XGBoost > Random Forest |

### 3. Cross-Validation Strategy
- **StratifiedKFold** (default for classification): preserves class ratios
- **KFold** (regression): random split
- **TimeSeriesSplit** (temporal data): no future leakage
- **GroupKFold** (grouped data): groups don't leak across folds
- **Typically 5 folds** (3 for large datasets, 10 for small)

### 4. Training Loop
```
For each model candidate:
  1. Train with cross-validation
  2. Record per-fold metrics
  3. Record mean ± std of metrics
  4. Record training time
  5. Save best model
```

### 5. Hyperparameter Tuning
- **Start with defaults** — modern libraries have good defaults
- **Optuna** for Bayesian optimization (50-100 trials)
- Key hyperparameters by model:
  - **LightGBM**: num_leaves, learning_rate, min_child_samples, subsample, colsample_bytree, reg_alpha, reg_lambda
  - **XGBoost**: max_depth, learning_rate, min_child_weight, subsample, colsample_bytree
  - **Random Forest**: n_estimators, max_depth, min_samples_leaf

### 6. Ensemble Methods (if needed)
- **Voting**: average predictions of diverse models
- **Stacking**: use model predictions as features for a meta-learner
- Only if single model doesn't meet threshold

## Common Pitfalls
- Skipping baselines and jumping to complex models
- Tuning on test data (use validation set or CV)
- Over-tuning (too many trials → overfitting to validation)
- Not recording training time (a 1% gain at 100× cost may not be worth it)

## Quality Checks
- [ ] Baseline established and documented
- [ ] CV strategy appropriate for the data
- [ ] At least 2-3 model types compared
- [ ] Metrics recorded with mean ± std
- [ ] Best model saved as artifact
- [ ] Training time recorded
