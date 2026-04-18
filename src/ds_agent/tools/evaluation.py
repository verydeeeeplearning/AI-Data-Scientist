"""Model evaluation tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="evaluate_model",
    description=(
        "Evaluate a trained model on test data. Computes metrics, generates error "
        "analysis, segment-level performance, calibration analysis, and feature "
        "importance (SHAP). Returns structured evaluation report."
    ),
    category="ds_modeling",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code for evaluation. Should load model and test data, compute metrics, generate plots.",
            },
            "model_path": {
                "type": "string",
                "description": "Path to the trained model file",
            },
            "test_data_path": {
                "type": "string",
                "description": "Path to the test dataset",
            },
            "target_column": {
                "type": "string",
                "description": "Name of the target variable",
            },
            "task_type": {
                "type": "string",
                "enum": [
                    "binary_classification",
                    "multiclass_classification",
                    "regression",
                ],
                "description": "Type of ML task",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory to save evaluation artifacts",
            },
            "timeout": {
                "type": "integer",
                "default": 300,
                "description": "Maximum execution time in seconds",
            },
        },
        "required": ["code", "model_path", "test_data_path", "target_column"],
    },
    timeout=300,
    prompt=(
        "Evaluates a trained model on test data with comprehensive metrics.\n\n"
        "## Injected Variables (USE THESE EXACT NAMES — UPPERCASE)\n"
        "The sandbox preamble injects these as module-level constants. "
        "Reference them directly; do NOT re-declare or use lowercase:\n"
        "- `MODEL_PATH` (str): path to the trained model file\n"
        "- `TEST_DATA_PATH` (str): path to the test dataset\n"
        "- `TARGET_COLUMN` (str): name of the target variable\n"
        "- `TASK_TYPE` (str | None): 'binary_classification' | 'multiclass_classification' | 'regression'\n"
        "- `OUTPUT_DIR` (str | None): directory for artifacts — **already created for you**\n\n"
        "## What to Report\n"
        "- Classification: accuracy, F1, AUC-ROC, confusion matrix\n"
        "- Regression: RMSE, MAE, R-squared, residual plots\n"
        "- Feature importance (SHAP preferred)\n"
        "- Compare against the baseline model\n"
        "- Check per-segment performance (by category, time period)\n\n"
        "## Example\n"
        "```python\n"
        "import joblib, pandas as pd, matplotlib.pyplot as plt\n"
        "from pathlib import Path\n"
        "model = joblib.load(MODEL_PATH)\n"
        "df = pd.read_csv(TEST_DATA_PATH)\n"
        "y = df[TARGET_COLUMN]\n"
        "X = df.drop(columns=[TARGET_COLUMN])\n"
        "pred = model.predict(X)\n"
        "fig, ax = plt.subplots()\n"
        "# OUTPUT_DIR already exists — just save into it\n"
        "fig.savefig(Path(OUTPUT_DIR) / 'confusion_matrix.png')\n"
        "```"
    ),
)
async def evaluate_model(
    code: str,
    model_path: str,
    test_data_path: str,
    target_column: str,
    task_type: str | None = None,
    output_dir: str | None = None,
    timeout: int = 300,
) -> str:
    # Preamble responsibilities:
    #  1. Inject named constants so LLM code doesn't need to guess paths
    #  2. Pre-create OUTPUT_DIR so plt.savefig / PIL don't FileNotFoundError
    #  3. Force matplotlib 'Agg' backend — the default Tk backend crashes
    #     with "main thread is not in main loop" / "Tcl_AsyncDelete" when
    #     subprocess tears down pyplot figures. Must happen BEFORE the
    #     LLM's code imports pyplot.
    preamble = (
        f"MODEL_PATH = {model_path!r}\n"
        f"TEST_DATA_PATH = {test_data_path!r}\n"
        f"TARGET_COLUMN = {target_column!r}\n"
        f"TASK_TYPE = {task_type!r}\n"
        f"OUTPUT_DIR = {output_dir!r}\n"
        "from pathlib import Path as _Path\n"
        "if OUTPUT_DIR:\n"
        "    _Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)\n"
        "try:\n"
        "    import matplotlib as _mpl\n"
        "    _mpl.use('Agg')\n"
        "except Exception:\n"
        "    pass\n"
    )
    full_code = preamble + code
    return await run_ds_sandbox(
        full_code,
        tool_name="evaluate_model",
        timeout=timeout,
        success_default="Model evaluation completed.",
    )
