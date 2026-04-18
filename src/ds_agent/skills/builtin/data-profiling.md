---
name: data-profiling
description: Systematic data quality assessment — schema, distributions, missing patterns, outliers
category: ds_methodology
tags: [data-quality, profiling, missing-values, outliers, schema]
version: "1.0.0"
author: builtin
token_estimate: 1000
related_skills: [scoping, eda]
---

# Data Profiling

## When to Use This Skill
- Immediately after loading a new dataset
- Before any EDA or feature engineering
- When data source changes or is updated

## Step-by-Step Procedure

### 1. Schema Analysis
- Use `data_loader()` to load and get basic stats
- Record: column count, row count, dtypes, memory usage
- Identify: numeric, categorical, datetime, text, ID columns

### 2. Missing Value Analysis
- Calculate missing % per column
- Identify patterns: MCAR (random), MAR (systematic), MNAR (informative)
- Flag columns with >50% missing — consider dropping
- Plan imputation strategy for remaining

### 3. Distribution Analysis
- Numeric: mean, median, std, skewness, kurtosis, quantiles
- Categorical: cardinality, top-N values, rare categories
- Check for: zero-variance columns, constant values, near-constant

### 4. Duplicate Detection
- Check for exact row duplicates
- Check for near-duplicates (same features, different IDs)

### 5. Outlier Detection
- IQR method (1.5×IQR rule) for numeric columns
- Z-score method (>3σ) as secondary check
- Document but don't remove yet — EDA will determine action

### 6. Target Variable Analysis (if known)
- Classification: class distribution, imbalance ratio
- Regression: distribution shape, range, outliers in target

### 7. Quality Grade Assignment
- **A**: <5% missing, <1% duplicates, no schema issues
- **B**: <15% missing, <5% duplicates, minor issues
- **C**: <30% missing, some issues
- **D**: >30% missing or severe issues

## Common Pitfalls
- Profiling on a sample that doesn't represent the full data
- Ignoring datetime parsing issues
- Not checking for mixed types within a column
- Treating ID columns as features

## Quality Checks
- [ ] All columns have dtype identified
- [ ] Missing values documented with patterns
- [ ] Outliers identified but not removed
- [ ] Target variable distribution assessed
- [ ] Quality grade assigned

## Output Expectations
- A `data_profile` artifact with comprehensive statistics in JSON format
