---
name: feature-engineering
description: Feature creation, encoding, scaling, missing value handling, and train/test splitting
category: ds_methodology
tags: [features, encoding, scaling, imputation, split, transformation]
version: "1.0.0"
author: builtin
token_estimate: 1200
related_skills: [eda, modeling]
---

# Feature Engineering

## When to Use This Skill
- After EDA is complete and hypotheses are formed
- Before model training
- When model performance needs improvement

## Step-by-Step Procedure

### 1. Feature Selection
- Drop: IDs, constants, near-zero variance, highly correlated pairs (>0.95)
- Keep: features with target correlation or domain importance
- Use EDA findings to guide selection

### 2. Missing Value Handling
- **Numeric**: median (robust), mean (if normal), KNN imputation (if patterns)
- **Categorical**: mode, "Unknown" category, indicator column
- **CRITICAL**: Fit imputers on TRAIN only, transform on val/test

### 3. Encoding
- **Ordinal**: LabelEncoder or manual mapping (low/medium/high → 0/1/2)
- **Nominal (low cardinality <10)**: OneHotEncoder
- **Nominal (high cardinality)**: TargetEncoder, FrequencyEncoder
- **CRITICAL**: Fit encoders on TRAIN only

### 4. Feature Creation
- **Interactions**: A × B, A / B, A - B for domain-meaningful pairs
- **Aggregations**: group-by statistics (mean, count, std per category)
- **Datetime**: year, month, day_of_week, hour, is_weekend, days_since
- **Text**: TF-IDF, word count, sentiment (if applicable)
- **Binning**: discretize continuous features into meaningful ranges

### 5. Scaling
- **StandardScaler**: for linear models (mean=0, std=1)
- **MinMaxScaler**: for neural nets, distance-based models
- **RobustScaler**: when outliers present
- Tree models (RF, XGBoost, LightGBM) typically DON'T need scaling

### 6. Train/Validation/Test Split
- **CRITICAL — do this BEFORE any fitting (imputation, encoding, scaling)**
- Default: 60% train / 20% validation / 20% test
- **Stratified** for classification (maintain class proportions)
- **Time-based** for time series (no future leakage)
- **Group-based** when rows aren't independent (same customer in one split)

### 7. Leakage Prevention Checklist
- [ ] No test data used during feature engineering
- [ ] Imputers/encoders/scalers fitted on train only
- [ ] No future information in time series features
- [ ] Target variable not used in feature creation
- [ ] No proxy features that encode the target

## Common Pitfalls
- Fitting transformers on the full dataset (data leakage!)
- OneHotEncoding high-cardinality features (dimension explosion)
- Not handling unseen categories in test data
- Scaling target variable in regression (sometimes needed, sometimes not)

## Quality Checks
- [ ] Train/val/test split done FIRST
- [ ] All transformations fit on train only
- [ ] No data leakage detected
- [ ] Feature matrix saved as artifact
- [ ] Feature names and transformations documented

## Output Expectations
- Train/val/test feature matrices saved as parquet
- Feature transformation pipeline saved (for inference)
