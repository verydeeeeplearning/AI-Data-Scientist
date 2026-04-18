"""Report generation tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="generate_report",
    description=(
        "Generate a comprehensive analysis report in Markdown or HTML format. "
        "Includes executive summary, methodology, data findings, model performance, "
        "and visualizations."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to generate the report.",
            },
            "project_dir": {
                "type": "string",
                "description": "Path to the project directory containing artifacts",
            },
            "output_path": {
                "type": "string",
                "description": "Path to save the generated report file",
            },
            "report_type": {
                "type": "string",
                "enum": ["technical", "executive", "model_card", "full"],
                "default": "full",
                "description": "Type of report",
            },
            "output_format": {
                "type": "string",
                "enum": ["markdown", "html"],
                "default": "markdown",
                "description": "Output file format",
            },
            "audience": {
                "type": "string",
                "enum": ["technical", "executive", "pm", "slack"],
                "description": "Optional audience hint exposed to the report generation code.",
            },
        },
        "required": ["code", "project_dir", "output_path"],
    },
    timeout=120,
    prompt=(
        "Generates a Markdown or HTML report from analysis results.\n\n"
        "## Report Types\n"
        "- technical: detailed methodology, all metrics, code references\n"
        "- executive: high-level findings, recommendations, business impact\n"
        "- model_card: model documentation (inputs, outputs, limitations)\n"
        "- full: all of the above combined\n\n"
        "## Guidelines\n"
        "- Reference plot files by relative path for inline display\n"
        "- Use Markdown tables for metric comparisons\n"
        "- Include actionable recommendations"
    ),
)
async def generate_report(
    code: str,
    project_dir: str,
    output_path: str,
    report_type: str = "full",
    output_format: str = "markdown",
    audience: str | None = None,
) -> str:
    preamble = (
        f"PROJECT_DIR = {project_dir!r}\n"
        f"OUTPUT_PATH = {output_path!r}\n"
        f"REPORT_TYPE = {report_type!r}\n"
        f"OUTPUT_FORMAT = {output_format!r}\n"
        f"AUDIENCE = {audience!r}\n"
    )
    return await run_ds_sandbox(
        preamble + code,
        tool_name="generate_report",
        timeout=120,
        success_default=f"Report saved to {output_path}",
    )
