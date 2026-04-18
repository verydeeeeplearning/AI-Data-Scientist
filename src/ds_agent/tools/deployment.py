"""Deployment configuration generation tool."""

from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.registry import tool


@tool(
    name="generate_deployment",
    description=(
        "Generate deployment configuration for a trained ML model. "
        "Creates Dockerfile, inference pipeline, monitoring config, and API endpoint."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to generate deployment artifacts.",
            },
            "model_path": {
                "type": "string",
                "description": "Path to the trained model file",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory to save deployment artifacts",
            },
            "deployment_target": {
                "type": "string",
                "enum": ["docker", "aws_lambda", "gcp_cloud_run", "kubernetes", "local"],
                "default": "docker",
                "description": "Target deployment platform",
            },
        },
        "required": ["code", "model_path", "output_dir"],
    },
    timeout=120,
    safety_level="caution",
    prompt=(
        "Generates deployment artifacts: Dockerfile, inference pipeline, API endpoint.\n\n"
        "## When to Use\n"
        "- After evaluation confirms model is ready for production\n\n"
        "## Guidelines\n"
        "- Include model versioning and dependency requirements\n"
        "- Add health check endpoint for monitoring\n"
        "- Document input/output schema for the API"
    ),
)
async def generate_deployment(
    code: str,
    model_path: str,
    output_dir: str,
    deployment_target: str = "docker",
) -> str:
    preamble = (
        f"MODEL_PATH = {model_path!r}\n"
        f"OUTPUT_DIR = {output_dir!r}\n"
        f"DEPLOYMENT_TARGET = {deployment_target!r}\n"
    )
    return await run_ds_sandbox(
        preamble + code,
        tool_name="generate_deployment",
        timeout=120,
        success_default=f"Deployment config saved to {output_dir}",
    )
