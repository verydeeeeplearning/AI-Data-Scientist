---
name: reporting
description: Generate comprehensive analysis reports — technical, executive, and model cards
category: ds_methodology
tags: [reporting, documentation, model-card, visualization, communication]
version: "1.0.0"
author: builtin
token_estimate: 800
related_skills: [evaluation, deployment]
---

# Reporting

## When to Use This Skill
- After model evaluation is complete
- When the user needs a deliverable document
- When documenting a completed project

## Step-by-Step Procedure

### 1. Executive Summary
- Problem statement (1-2 sentences)
- Approach taken (1-2 sentences)
- Key results (metrics, business impact)
- Recommendation

### 2. Data Section
- Dataset description (source, size, timeframe)
- Key quality findings from profiling
- Feature engineering decisions and rationale

### 3. Methodology Section
- Models evaluated and why
- Cross-validation strategy
- Hyperparameter tuning approach

### 4. Results Section
- Model comparison table
- Best model performance metrics
- Key visualizations (embed saved plot paths)
- Feature importance

### 5. Limitations and Risks
- Data quality issues that remain
- Model failure modes identified in error analysis
- Fairness concerns
- Known blind spots

### 6. Recommendations
- Deploy or iterate?
- Monitoring plan
- Data collection improvements
- Future model improvements

### 7. Model Card (if applicable)
- Model details: algorithm, version, date
- Intended use and users
- Performance metrics per subgroup
- Limitations and ethical considerations
- Training data description

## Quality Checks
- [ ] Executive summary is accessible to non-technical readers
- [ ] All claims supported by data/metrics
- [ ] Visualizations are referenced and readable
- [ ] Limitations honestly stated
- [ ] Next steps are actionable
