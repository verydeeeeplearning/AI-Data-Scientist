"""Feature engineering tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="feature_engineer",
    description=(
        "Execute feature engineering code with automatic INPUT_PATH/OUTPUT_PATH/TARGET_COLUMN injection. "
        "Use for encoding, scaling, imputation, train/test splits, and derived feature creation. "
        "Prefer this over 'execute_code' for any feature transformation — it tracks the DS workflow stage "
        "and enables leakage detection hooks."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code for feature engineering. Should load data, create features, save results.",
            },
            "input_path": {
                "type": "string",
                "description": "Path to the input dataset",
            },
            "output_path": {
                "type": "string",
                "description": "Path to save the engineered feature matrix",
            },
            "target_column": {
                "type": "string",
                "description": "Target variable name",
            },
            "timeout": {
                "type": "integer",
                "default": 180,
                "description": "Maximum execution time in seconds",
            },
        },
        "required": ["code", "input_path", "output_path"],
    },
    timeout=180,
    safety_level="caution",
    prompt=(
        "Runs feature engineering code: encoding, scaling, imputation, splits.\n\n"
        "## Injected Variables (USE THESE EXACT NAMES — UPPERCASE)\n"
        "The sandbox preamble injects these as module-level constants. "
        "Reference them directly; do NOT re-declare or use lowercase:\n"
        "- `INPUT_PATH` (str): path to the input dataset\n"
        "- `OUTPUT_PATH` (str): path to save the engineered feature matrix — "
        "**parent directory is pre-created for you**\n"
        "- `TARGET_COLUMN` (str | None): target variable name\n\n"
        "## Key Rules\n"
        "- Split data BEFORE transformations to prevent leakage\n"
        "- Fit encoders/scalers on TRAIN only, transform both train and test\n"
        "- Handle missing values based on mechanism (MCAR->mean, MAR->model)\n"
        "- Tree models don't need scaling; linear models do\n"
        "- High-cardinality categoricals: target encoding or frequency encoding\n\n"
        "## Example\n"
        "```python\n"
        "import pandas as pd\n"
        "df = pd.read_csv(INPUT_PATH)\n"
        "y = df[TARGET_COLUMN]\n"
        "# ... transform ...\n"
        "df.to_csv(OUTPUT_PATH, index=False)\n"
        "```"
    ),
)
async def feature_engineer(
    code: str,
    input_path: str,
    output_path: str,
    target_column: str | None = None,
    timeout: int = 180,
) -> str:
    preamble = (
        f"INPUT_PATH = {input_path!r}\n"
        f"OUTPUT_PATH = {output_path!r}\n"
        f"TARGET_COLUMN = {target_column!r}\n"
        "from pathlib import Path as _Path\n"
        "_Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)\n"
    )
    full_code = preamble + code
    return await run_ds_sandbox(
        full_code,
        tool_name="feature_engineer",
        timeout=timeout,
        success_default=f"Feature engineering completed. Output: {output_path}",
    )
