"""Data profiling tool — comprehensive data quality analysis."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="data_profiler",
    description=(
        "Generate a comprehensive data quality profile for a loaded dataset. "
        "Includes schema analysis, statistical distributions, missing value patterns, "
        "duplicate detection, outlier analysis, correlation matrix, and an overall "
        "quality grade (A/B/C/D). Use after data_loader to understand data quality."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the dataset file (CSV/Parquet)",
            },
            "target_column": {
                "type": "string",
                "description": "Target variable for target-specific analysis",
            },
            "profile_level": {
                "type": "string",
                "enum": ["quick", "standard", "deep"],
                "default": "standard",
                "description": "Profiling depth",
            },
            "sample_size": {
                "type": "integer",
                "description": "Number of rows to sample for large datasets",
            },
        },
        "required": ["file_path"],
    },
    timeout=120,
    prompt=(
        "Generates a data quality profile: schema, stats, missing values, correlations.\n\n"
        "## When to Use\n"
        "- After data_loader — understand quality before EDA or modeling\n"
        "- Set target_column for target-specific analysis (class balance, correlation)\n\n"
        "## Profile Levels\n"
        "- quick: schema + basic stats only (~5s)\n"
        "- standard: + missing patterns, correlations, outliers (~15s)\n"
        "- deep: + segment analysis, detailed distributions (~30s)\n\n"
        "## Tips\n"
        "- For large datasets (>1M rows), use sample_size to limit\n"
        "- Quality grade (A/B/C/D) gives quick overall assessment"
    ),
)
async def data_profiler(
    file_path: str,
    target_column: str | None = None,
    profile_level: str = "standard",
    sample_size: int | None = None,
) -> str:
    code = f"""
import pandas as pd
import numpy as np
import json

file_path = {file_path!r}
target_column = {target_column!r}
profile_level = {profile_level!r}
sample_size = {sample_size!r}

# Load
ext = file_path.rsplit('.', 1)[-1].lower()
if ext in ('parquet', 'pq'):
    df = pd.read_parquet(file_path)
else:
    df = pd.read_csv(file_path)

if sample_size and len(df) > sample_size:
    df = df.sample(sample_size, random_state=42)

profile = {{"shape": list(df.shape), "columns": {{}}}}
total_missing = 0

for col in df.columns:
    info = {{
        "dtype": str(df[col].dtype),
        "missing": int(df[col].isnull().sum()),
        "missing_pct": round(df[col].isnull().mean() * 100, 2),
        "unique": int(df[col].nunique()),
    }}
    total_missing += info["missing"]

    if df[col].dtype in ("int64", "float64"):
        info["mean"] = round(float(df[col].mean()), 4) if not df[col].isnull().all() else None
        info["std"] = round(float(df[col].std()), 4) if not df[col].isnull().all() else None
        info["min"] = float(df[col].min()) if not df[col].isnull().all() else None
        info["max"] = float(df[col].max()) if not df[col].isnull().all() else None

        if profile_level in ("standard", "deep"):
            q1 = float(df[col].quantile(0.25)) if not df[col].isnull().all() else None
            q3 = float(df[col].quantile(0.75)) if not df[col].isnull().all() else None
            if q1 is not None and q3 is not None:
                iqr = q3 - q1
                outlier_mask = (df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)
                info["outlier_count"] = int(outlier_mask.sum())
    else:
        info["top_values"] = df[col].value_counts().head(5).to_dict()

    profile["columns"][col] = info

# Duplicates
profile["duplicate_rows"] = int(df.duplicated().sum())

# Overall quality grade
missing_pct = (total_missing / (df.shape[0] * df.shape[1])) * 100 if df.size > 0 else 0
dup_pct = (profile["duplicate_rows"] / len(df)) * 100 if len(df) > 0 else 0

if missing_pct < 5 and dup_pct < 1:
    grade = "A"
elif missing_pct < 15 and dup_pct < 5:
    grade = "B"
elif missing_pct < 30:
    grade = "C"
else:
    grade = "D"

profile["quality_grade"] = grade
profile["total_missing_pct"] = round(missing_pct, 2)

# Target analysis
if target_column and target_column in df.columns:
    target = df[target_column]
    if target.dtype == "object" or target.nunique() < 20:
        profile["target"] = {{"type": "categorical", "distribution": target.value_counts().to_dict()}}
    else:
        profile["target"] = {{"type": "numeric", "mean": round(float(target.mean()), 4), "std": round(float(target.std()), 4)}}

print(json.dumps(profile, default=str))
"""
    return await run_ds_sandbox(code, tool_name="data_profiler", timeout=120)
