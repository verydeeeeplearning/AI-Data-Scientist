"""Exploratory data analysis tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="run_eda",
    description=(
        "Execute exploratory data analysis code with automatic DATA_PATH/OUTPUT_DIR injection. "
        "Use for visualizations (matplotlib/seaborn/plotly), statistical tests, and hypothesis testing. "
        "Prefer this over 'execute_code' for any EDA work — it pre-configures data path and output directory. "
        "Returns analysis results and paths to generated plot files."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code for EDA. Use pandas, matplotlib/seaborn. Save plots with plt.savefig().",
            },
            "data_path": {
                "type": "string",
                "description": "Path to the dataset file to analyze",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory to save generated plots",
            },
            "timeout": {
                "type": "integer",
                "default": 120,
                "description": "Maximum execution time in seconds",
            },
        },
        "required": ["code", "data_path"],
    },
    timeout=120,
    prompt=(
        "Runs EDA code and saves visualizations as plot files.\n\n"
        "## Injected Variables (USE THESE EXACT NAMES — UPPERCASE)\n"
        "The sandbox preamble injects these as module-level constants. "
        "Reference them directly; do NOT re-declare or use lowercase:\n"
        "- `DATA_PATH` (str): path to the dataset file to analyze\n"
        "- `OUTPUT_DIR` (str | None): directory for plots — **pre-created for you**\n\n"
        "## When to Use\n"
        "- After profiling — visualize distributions, correlations, patterns\n\n"
        "## Guidelines\n"
        "- Always use `plt.savefig(Path(OUTPUT_DIR) / 'name.png')` — do NOT plt.show()\n"
        "- Common: histograms, boxplots, scatter, correlation heatmap, pair plot\n"
        "- Always add titles and axis labels to plots\n"
        "- Use plt.close() after each figure to avoid memory issues\n\n"
        "## Example\n"
        "```python\n"
        "import pandas as pd, matplotlib.pyplot as plt\n"
        "from pathlib import Path\n"
        "df = pd.read_csv(DATA_PATH)\n"
        "fig, ax = plt.subplots()\n"
        "df.hist(ax=ax)\n"
        "fig.savefig(Path(OUTPUT_DIR) / 'hist.png')\n"
        "plt.close(fig)\n"
        "```"
    ),
)
async def run_eda(
    code: str, data_path: str, output_dir: str | None = None, timeout: int = 120
) -> str:
    # Inject data_path and output_dir as variables, pre-create OUTPUT_DIR,
    # and force matplotlib 'Agg' backend — the default Tk backend crashes on
    # subprocess teardown with "main thread is not in main loop".
    preamble = (
        f"DATA_PATH = {data_path!r}\n"
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
        tool_name="run_eda",
        timeout=timeout,
        success_default="(EDA completed, no stdout output)",
    )
