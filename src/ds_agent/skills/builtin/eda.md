---
name: eda
description: Exploratory data analysis — visualizations, statistical tests, hypothesis generation
category: ds_methodology
tags: [eda, visualization, statistics, correlation, hypothesis]
version: "1.0.0"
author: builtin
token_estimate: 1100
related_skills: [data-profiling, feature-engineering]
---

# Exploratory Data Analysis (EDA)

## When to Use This Skill
- After data profiling is complete
- When you need to understand relationships between features
- Before feature engineering to form hypotheses
- When the user asks "what's interesting in this data?"

## Step-by-Step Procedure

### 1. Univariate Analysis
- **Numeric**: histograms, box plots, KDE plots
- **Categorical**: bar charts, value counts
- **Datetime**: time series line plots, seasonality check
- Save all plots to artifacts directory

### 2. Bivariate Analysis (Feature vs Target)
- **Numeric → Numeric target**: scatter plots, correlation
- **Numeric → Categorical target**: box plots by class, violin plots
- **Categorical → Target**: grouped bar charts, cross-tabs
- Calculate correlation matrix (Pearson, Spearman)

### 3. Statistical Tests
- **Numeric groups**: t-test (2 groups), ANOVA (3+ groups)
- **Categorical associations**: Chi-square test
- **Correlations**: Pearson (linear), Spearman (monotonic)
- **Normality**: Shapiro-Wilk test (if needed)
- Report p-values with significance threshold (typically 0.05)

### 4. Multivariate Analysis
- Correlation heatmap (top-N most correlated features)
- Pair plots for top features (limit to ~5-6 features)
- PCA visualization (2D/3D) if high-dimensional

### 5. Hypothesis Generation
- Form hypotheses based on observed patterns
- Document surprising findings
- Identify potential feature interactions
- Note features that seem highly predictive (but check for leakage)

### 6. EDA Summary
- Top 5-10 key findings
- Recommended features for modeling
- Identified issues (multicollinearity, leakage risks)

## Common Pitfalls
- Making too many plots without extracting insights
- Not saving plots as artifacts
- Ignoring statistical significance (seeing patterns in noise)
- Feature leakage — a feature strongly correlated with target may encode it

## Quality Checks
- [ ] All key features visualized
- [ ] Correlation matrix computed
- [ ] Statistical tests run where appropriate
- [ ] Plots saved as artifact files
- [ ] Key findings documented

## Example Patterns
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv(DATA_PATH)
# Correlation heatmap
plt.figure(figsize=(12, 8))
sns.heatmap(df.select_dtypes('number').corr(), annot=True, cmap='coolwarm', center=0)
plt.title('Feature Correlations')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/correlation_heatmap.png', dpi=150)
plt.close()
```
