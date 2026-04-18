---
name: scoping
description: Define ML problem scope, success criteria, and constraints before starting analysis
category: ds_methodology
tags: [problem-definition, requirements, scope, stakeholder, kpi]
version: "1.0.0"
author: builtin
token_estimate: 1200
related_skills: [data-profiling, modeling]
---

# ML Problem Scoping

## When to Use This Skill
- At the very beginning of any data science project
- When the user provides a vague request ("analyze this data", "predict X")
- When switching to a new dataset or problem domain
- Before any EDA or modeling work

## Step-by-Step Procedure

### 1. Clarify the Business Problem
- **Ask**: What decision will this model inform?
- **Ask**: What is the current baseline (human process, simple rule)?
- **Ask**: What is the cost of wrong predictions (false positives vs false negatives)?
- If the user hasn't specified, **ask_user()** to clarify

### 2. Define the ML Task Type
Choose the correct formulation:
- **Classification**: binary, multiclass, multi-label
- **Regression**: single target, multi-output
- **Time Series**: forecasting, anomaly detection
- **Clustering**: customer segmentation, pattern discovery
- **Ranking**: recommendation, search relevance
- **Anomaly Detection**: fraud, system failures

### 3. Identify the Target Variable
- Must be clearly defined and measurable
- Check if target exists in the data or needs to be engineered
- Watch for **target leakage** — features that encode the target

### 4. Define Success Metrics
- **Classification**: Accuracy, F1, AUC-ROC, Precision@K, Log Loss
- **Regression**: RMSE, MAE, MAPE, R²
- **Ranking**: NDCG, MAP, MRR
- Set a **minimum acceptable threshold** with the user

### 5. Identify Constraints
- **Data constraints**: size, quality, availability, privacy (PII/GDPR)
- **Model constraints**: interpretability, latency, memory
- **Time constraints**: deadline for delivery
- **Ethical constraints**: fairness across protected groups

### 6. Define Deliverables
- Trained model file? API endpoint? Dashboard? Report?
- Model card with limitations and intended use?
- Monitoring plan?

## Key Decisions
- If the problem is ambiguous, **always ask the user** before assuming
- If multiple metrics conflict (precision vs recall), ask for priority
- If data is insufficient, recommend data collection before modeling

## Common Pitfalls
- Starting modeling without understanding the business context
- Optimizing the wrong metric (accuracy on imbalanced data)
- Ignoring deployment constraints during scoping
- Assuming the target variable is clean and well-defined

## Quality Checks
- [ ] Business question is clearly stated
- [ ] ML task type is identified
- [ ] Target variable is defined and exists in data
- [ ] Success metric and threshold are set
- [ ] Constraints are documented
- [ ] Deliverables are agreed upon

## Output Expectations
- A `task_spec` artifact containing: problem statement, task type, target, metrics, constraints
