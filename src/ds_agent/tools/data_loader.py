"""Data loading tool — loads datasets and returns summary."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="data_loader",
    description=(
        "Load a dataset from CSV, Parquet, Excel, JSON, or SQL source. "
        "Returns a summary including shape, dtypes, first rows, memory usage, "
        "and basic statistics. Use this as the first step when working with a new dataset."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the data file (CSV, Parquet, Excel, JSON)",
            },
            "file_type": {
                "type": "string",
                "enum": ["csv", "parquet", "excel", "json"],
                "description": "Type of data source. Auto-detected from extension if omitted.",
            },
            "sample_rows": {
                "type": "integer",
                "default": 5,
                "description": "Number of rows to include in the head preview",
            },
            "encoding": {
                "type": "string",
                "default": "utf-8",
                "description": "File encoding (for CSV/JSON)",
            },
            "separator": {
                "type": "string",
                "default": ",",
                "description": "Column separator (for CSV)",
            },
            "nrows": {
                "type": "integer",
                "description": "Maximum number of rows to load. Omit to load all.",
            },
        },
        "required": ["file_path"],
    },
    timeout=60,
    prompt=(
        "Loads data from file and returns a summary with shape, dtypes, and head.\n\n"
        "## When to Use\n"
        "- First step in any analysis — load data before profiling or EDA\n"
        "- Omit file_type to auto-detect format from extension\n\n"
        "## Important\n"
        "- CSV with non-ASCII (Korean, Japanese): specify encoding='utf-8'\n"
        "- Large files (>100MB): use nrows to sample first\n"
        "- Excel: reads first sheet by default\n"
        "- After loading, run data_profiler to understand data quality\n\n"
        "## Do NOT Use When\n"
        "- File is already loaded in a previous step\n"
        "- You need arbitrary pandas code (use execute_code instead)"
    ),
)
async def data_loader(
    file_path: str,
    file_type: str | None = None,
    sample_rows: int = 5,
    encoding: str = "utf-8",
    separator: str = ",",
    nrows: int | None = None,
) -> str:
    code = f"""
import pandas as pd
import json

file_path = {file_path!r}
file_type = {file_type!r}
sample_rows = {sample_rows}
encoding = {encoding!r}
separator = {separator!r}
nrows = {nrows!r}

# Auto-detect file type
if file_type is None:
    ext = file_path.rsplit('.', 1)[-1].lower()
    file_type = {{"csv": "csv", "parquet": "parquet", "pq": "parquet",
                  "xlsx": "excel", "xls": "excel", "json": "json"}}.get(ext, "csv")

# Load data
if file_type == "csv":
    df = pd.read_csv(file_path, encoding=encoding, sep=separator, nrows=nrows)
elif file_type == "parquet":
    df = pd.read_parquet(file_path)
    if nrows:
        df = df.head(nrows)
elif file_type == "excel":
    df = pd.read_excel(file_path, nrows=nrows)
elif file_type == "json":
    df = pd.read_json(file_path, encoding=encoding, nrows=nrows)
else:
    df = pd.read_csv(file_path, nrows=nrows)

# Build summary
summary = {{
    "shape": list(df.shape),
    "columns": list(df.columns),
    "dtypes": {{col: str(dtype) for col, dtype in df.dtypes.items()}},
    "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
    "missing": {{col: int(count) for col, count in df.isnull().sum().items() if count > 0}},
    "head": df.head(sample_rows).to_dict(orient="records"),
    "describe": df.describe(include="all").to_dict(),
}}
print(json.dumps(summary, default=str))
"""
    return await run_ds_sandbox(code, tool_name="data_loader", timeout=60)
