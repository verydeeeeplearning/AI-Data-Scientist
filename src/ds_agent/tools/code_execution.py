"""General-purpose Python code execution tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="execute_code",
    description=(
        "Execute general-purpose Python code in a sandboxed subprocess. "
        "Use ONLY for custom operations not covered by dedicated tools. "
        "For data loading use 'data_loader', for EDA use 'run_eda', "
        "for feature engineering use 'feature_engineer', "
        "for model training use 'train_model'. "
        "Print results to stdout for the agent to see."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
            "timeout": {
                "type": "integer",
                "default": 120,
                "description": "Maximum execution time in seconds",
            },
        },
        "required": ["code"],
    },
    timeout=120,
    safety_level="caution",
    prompt=(
        "Executes Python code in an isolated subprocess.\n\n"
        "## When to Use\n"
        "- Custom analysis that no dedicated tool covers\n"
        "- Complex data transformations or aggregations\n"
        "- Creating visualizations with matplotlib/seaborn\n\n"
        "## Guidelines\n"
        "- Available: pandas, numpy, sklearn, matplotlib, seaborn, lightgbm, xgboost, joblib, optuna\n"
        "- Print results explicitly — only stdout is captured\n"
        "- For plots: save with plt.savefig(), do NOT use plt.show()\n"
        "- For DataFrames: print .head() or .shape — not the full frame\n\n"
        "## Do NOT\n"
        "- Use os.system(), subprocess, or network access\n"
        "- Modify files outside the workspace directory\n"
        "- Run infinite loops without break conditions"
    ),
)
async def execute_code(code: str, timeout: int = 120) -> str:
    # Force non-interactive matplotlib backend — the default Tk backend
    # crashes on subprocess teardown with "main thread is not in main loop".
    # Wrapped so non-matplotlib code is unaffected.
    preamble = (
        "try:\n"
        "    import matplotlib as _mpl\n"
        "    _mpl.use('Agg')\n"
        "except Exception:\n"
        "    pass\n"
    )
    return await run_ds_sandbox(
        preamble + code,
        tool_name="execute_code",
        timeout=timeout,
        success_default="(no output)",
    )
