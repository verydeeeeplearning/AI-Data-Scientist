---
name: deployment
description: ML model deployment — API endpoints, Docker, monitoring, and rollback
category: ds_methodology
tags: [deployment, api, docker, monitoring, inference, mlops]
version: "1.0.0"
author: builtin
token_estimate: 800
related_skills: [evaluation, reporting]
---

# Deployment

## When to Use This Skill
- After a model is approved for production use
- When generating deployment artifacts
- When setting up monitoring

## Step-by-Step Procedure

### 1. Inference Pipeline
- Create a self-contained prediction script
- Include: data loading, preprocessing, prediction, postprocessing
- Use the SAME transformations as training (saved pipeline)

### 2. API Endpoint
- Default: FastAPI with `/predict` endpoint
- Input validation with Pydantic models
- Health check endpoint `/health`
- Versioned endpoint `/v1/predict`

### 3. Containerization
- Dockerfile with minimal base image
- Pin all dependency versions
- Multi-stage build (builder + runtime)
- Non-root user for security

### 4. Monitoring Setup
- **Data drift**: monitor input feature distributions
- **Performance drift**: track prediction distribution, latency
- **Alerts**: set thresholds for drift metrics
- Log predictions for audit trail

### 5. Testing
- Unit tests for preprocessing pipeline
- Integration tests for API endpoint
- Load tests for latency requirements

### 6. Rollback Plan
- Keep previous model version available
- Blue-green or canary deployment strategy
- Automated rollback on metric degradation

## Common Pitfalls
- Training/serving skew (different preprocessing in train vs inference)
- Not pinning dependency versions
- No monitoring after deployment
- Not testing with realistic input data

## Quality Checks
- [ ] Inference pipeline produces same results as training evaluation
- [ ] API endpoint tested with sample inputs
- [ ] Docker image builds and runs
- [ ] Monitoring configured
- [ ] Rollback procedure documented
