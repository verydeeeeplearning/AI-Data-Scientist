"""Model training tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="train_model",
    description=(
        "Train a machine learning model with automatic DATA_PATH/TARGET_COLUMN/MODEL_OUTPUT_PATH injection. "
        "Use for all model training — supports scikit-learn, LightGBM, XGBoost, CatBoost, Optuna. "
        "Prefer this over 'execute_code' for training — it tracks experiments, enables overfitting detection, "
        "and enforces baseline comparison via hooks."
    ),
    category="ds_modeling",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code for model training. Should load data, train model, evaluate, and save.",
            },
            "data_path": {
                "type": "string",
                "description": "Path to the feature matrix file",
            },
            "target_column": {
                "type": "string",
                "description": "Name of the target variable column",
            },
            "model_type": {
                "type": "string",
                "description": "Model algorithm (e.g., lightgbm, xgboost, random_forest)",
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
            "model_output_path": {
                "type": "string",
                "description": "Path to save the trained model file",
            },
            "timeout": {
                "type": "integer",
                "default": 900,
                "description": "Maximum execution time in seconds (default 15 min)",
            },
        },
        "required": ["code", "data_path", "target_column"],
    },
    timeout=900,
    safety_level="caution",
    prompt=(
        "Trains an ML model with cross-validation.\n\n"
        "## Injected Variables (USE THESE EXACT NAMES — UPPERCASE)\n"
        "The sandbox preamble injects these as module-level constants. "
        "Reference them directly; do NOT re-declare or use lowercase:\n"
        "- `DATA_PATH` (str): path to the feature matrix file\n"
        "- `TARGET_COLUMN` (str): name of the target variable\n"
        "- `MODEL_TYPE` (str | None): requested algorithm\n"
        "- `TASK_TYPE` (str | None): 'binary_classification' | 'multiclass_classification' | 'regression'\n"
        "- `MODEL_OUTPUT_PATH` (str | None): where to save the trained model — "
        "**parent directory is pre-created for you**\n\n"
        "## Strategy\n"
        "- Start simple (LogisticRegression/LinearRegression) as baseline\n"
        "- Then tree ensembles (RandomForest -> LightGBM/XGBoost)\n"
        "- Always 5-fold CV; report mean +/- std\n\n"
        "## Key Rules\n"
        "- Set random_state for reproducibility\n"
        "- Check overfitting: large train-validation gap = overfit\n"
        "- Save model with `joblib.dump(model, MODEL_OUTPUT_PATH)`\n"
        "- Handle class imbalance (class_weight or SMOTE)"
    ),
)
async def train_model(
    code: str,
    data_path: str,
    target_column: str,
    model_type: str | None = None,
    task_type: str | None = None,
    model_output_path: str | None = None,
    timeout: int = 900,
) -> str:
    preamble = (
        f"DATA_PATH = {data_path!r}\n"
        f"TARGET_COLUMN = {target_column!r}\n"
        f"MODEL_TYPE = {model_type!r}\n"
        f"TASK_TYPE = {task_type!r}\n"
        f"MODEL_OUTPUT_PATH = {model_output_path!r}\n"
        "from pathlib import Path as _Path\n"
        "if MODEL_OUTPUT_PATH:\n"
        "    _Path(MODEL_OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)\n"
    )
    full_code = preamble + code
    return await run_ds_sandbox(
        full_code,
        tool_name="train_model",
        timeout=timeout,
        success_default="Model training completed.",
    )
