# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DS Agent API backend.

Bundles the FastAPI server into a single-directory executable.
Electron's main process spawns this binary.

Usage:
    pyinstaller ds-agent-api.spec
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    collect_all,
)

block_cipher = None

# Project root
ROOT = os.path.abspath('.')
SRC = os.path.join(ROOT, 'src')

# ML stack — RFC_2026-04_ml_deps_policy.md. Packages with native DLLs
# (xgboost, lightgbm, some sklearn/scipy subs) require collect_dynamic_libs;
# pure-Python packages only need submodule collection. collect_all bundles
# everything (code + data + libs) which is safest for xgboost/lightgbm.
ML_HIDDEN = []
ML_DATAS = []
ML_BINARIES = []

# Packages with native binaries. collect_all() can crash when a package has
# optional/test submodules that fail to import at enumeration time (xgboost
# 3.x does exactly this via xgboost.testing). We instead:
#   1) collect submodules with an explicit filter,
#   2) collect data files (VERSION etc.),
#   3) add the native DLLs explicitly using the known layout.
def _safe_submodules(pkg, *, skip_substrings=()):
    try:
        names = collect_submodules(pkg)
    except Exception as e:
        print(f"[spec] collect_submodules({pkg!r}) failed: {e}")
        return [pkg]
    return [n for n in names if not any(s in n for s in skip_substrings)]

for _pkg, _skip in (
    ("xgboost", ("testing", "dask", "spark", "federated")),
    ("lightgbm", ("dask", "sklearn_compat")),
):
    ML_HIDDEN.extend(_safe_submodules(_pkg, skip_substrings=_skip))
    try:
        ML_DATAS.extend(collect_data_files(_pkg))
    except Exception as e:
        print(f"[spec] collect_data_files({_pkg!r}) failed: {e}")
    try:
        ML_BINARIES.extend(collect_dynamic_libs(_pkg))
    except Exception as e:
        print(f"[spec] collect_dynamic_libs({_pkg!r}) failed: {e}")

# Locate the project's .venv site-packages robustly — PyInstaller may run
# the spec inside a different interpreter, so sysconfig isn't reliable.
_VENV_SITE = os.path.join(ROOT, ".venv", "Lib", "site-packages")
if not os.path.isdir(_VENV_SITE):
    # Fallback: current sys.path
    import sys as _sys_spec
    _VENV_SITE = next(
        (p for p in _sys_spec.path if p.endswith("site-packages") and os.path.isdir(p)),
        _VENV_SITE,
    )
print(f"[spec] resolved venv site-packages: {_VENV_SITE}")

# Explicit native DLLs + layout-sensitive data files. Target path is the
# directory relative to the frozen _internal/ root.
_explicit_binaries = [
    ("xgboost/lib/xgboost.dll", "xgboost/lib"),
    ("lightgbm/lib/lib_lightgbm.dll", "lightgbm/lib"),
    ("lightgbm/bin/lib_lightgbm.dll", "lightgbm/bin"),
]
_explicit_datas = [
    ("xgboost/VERSION", "xgboost"),
    ("lightgbm/VERSION.txt", "lightgbm"),
]
for _rel, _dest in _explicit_binaries:
    _full = os.path.join(_VENV_SITE, _rel.replace("/", os.sep))
    if os.path.exists(_full):
        ML_BINARIES.append((_full, _dest))
        print(f"[spec] + binary {_rel} -> {_dest}")
    else:
        print(f"[spec] SKIP binary (not found): {_full}")
for _rel, _dest in _explicit_datas:
    _full = os.path.join(_VENV_SITE, _rel.replace("/", os.sep))
    if os.path.exists(_full):
        ML_DATAS.append((_full, _dest))
        print(f"[spec] + data {_rel} -> {_dest}")

# Pure-Python (mostly) packages — submodules + data files
for pkg in ("sklearn", "scipy", "matplotlib", "seaborn", "optuna", "joblib"):
    try:
        ML_HIDDEN.extend(collect_submodules(pkg))
    except Exception:
        ML_HIDDEN.append(pkg)
    try:
        ML_DATAS.extend(collect_data_files(pkg))
    except Exception:
        pass
    try:
        ML_BINARIES.extend(collect_dynamic_libs(pkg))
    except Exception:
        pass

# Collect skill markdown files (data, not code)
skills_dir = os.path.join(SRC, 'ds_agent', 'skills', 'builtin')
skills_data = []
if os.path.isdir(skills_dir):
    for root_dir, _dirs, files in os.walk(skills_dir):
        for f in files:
            if f.endswith('.md'):
                full = os.path.join(root_dir, f)
                rel = os.path.relpath(root_dir, SRC)
                skills_data.append((full, rel))

a = Analysis(
    [os.path.join(SRC, 'ds_agent', 'api', 'app.py')],
    pathex=[SRC],
    binaries=ML_BINARIES,
    datas=skills_data + ML_DATAS,
    hiddenimports=[
        # Core
        'ds_agent',
        'ds_agent.api',
        'ds_agent.api.app',
        'ds_agent.api.callbacks',
        'ds_agent.api.ws_handler',
        'ds_agent.api.routes',
        'ds_agent.api.routes.status',
        'ds_agent.api.routes.config',
        'ds_agent.api.routes.files',
        # Agent
        'ds_agent.agent',
        'ds_agent.agent.core',
        'ds_agent.agent.prompt_builder',
        'ds_agent.agent.context_manager',
        'ds_agent.agent.budget_tracker',
        'ds_agent.agent.callbacks',
        # Domain
        'ds_agent.domain',
        'ds_agent.domain.entities',
        'ds_agent.domain.entities.messages',
        'ds_agent.domain.entities.provider_models',
        'ds_agent.domain.value_objects',
        'ds_agent.domain.value_objects.budget',
        'ds_agent.domain.interfaces',
        'ds_agent.domain.interfaces.llm_provider',
        # Config
        'ds_agent.config',
        'ds_agent.config.schema',
        'ds_agent.config.loader',
        # Providers
        'ds_agent.providers',
        'ds_agent.providers.base',
        'ds_agent.providers.router',
        'ds_agent.providers.anthropic',
        'ds_agent.providers.openai_provider',
        'ds_agent.providers.litellm_provider',
        'ds_agent.providers.ollama',
        'ds_agent.providers.local_discovery',
        'ds_agent.providers.codex_oauth',
        'ds_agent.providers.gemini_oauth',
        'ds_agent.providers.pricing',
        # Tools
        'ds_agent.tools',
        'ds_agent.tools.registry',
        'ds_agent.tools.sandbox',
        'ds_agent.tools.code_execution',
        'ds_agent.tools.file_ops',
        'ds_agent.tools.data_loader',
        'ds_agent.tools.data_profiler',
        'ds_agent.tools.eda',
        'ds_agent.tools.feature_eng',
        'ds_agent.tools.modeling',
        'ds_agent.tools.evaluation',
        'ds_agent.tools.reporting',
        'ds_agent.tools.deployment',
        'ds_agent.tools.web_search',
        'ds_agent.tools.user_interaction',
        # Telegram operator gateway (lazy-imported by ws_handler / app.py lifespan)
        'ds_agent.gateway',
        'ds_agent.gateway.bot_supervisor',
        'ds_agent.gateway.telegram_runner',
        'ds_agent.gateway.telegram_strings',
        'ds_agent.gateway.telegram_semantic',
        'ds_agent.gateway.session_manager',
        'ds_agent.channels.bundled.telegram',
        'ds_agent.channels.bundled.telegram.plugin',
        'ds_agent.channels.bundled.telegram.callback_handler',
        'ds_agent.channels.bundled.telegram.message_builder',
        'ds_agent.infrastructure.telegram',
        'ds_agent.infrastructure.telegram.telegram_api_client',
        'ds_agent.application.ports.telegram_transport_port',
        'ds_agent.application.use_cases.pair_telegram_chat_usecase',
        'ds_agent.domain.notification',
        'ds_agent.domain.notification.pairing_state',
        'ds_agent.domain.errors.telegram_errors',
        'telegram',
        'telegram.ext',
        'ds_agent.tools.memory_tools',
        'ds_agent.tools.skill_tools',
        # Skills
        'ds_agent.skills',
        'ds_agent.skills.hub',
        'ds_agent.skills.parser',
        # Memory (session_db entry removed 2026-04-18 by S8 — module never existed, cleared from cleanup)
        'ds_agent.memory',
        'ds_agent.memory.experiment_log',
        'ds_agent.memory.code_registry',
        'ds_agent.memory.domain_kb',
        'ds_agent.memory.project_store',
        # Decision OS / review flow
        'ds_agent.infrastructure.decision_os_container',
        'ds_agent.infrastructure.importers.yaml_rollback_plan_loader',
        'ds_agent.infrastructure.persistence.feature_registry_store',
        'ds_agent.infrastructure.persistence.model_registry_store',
        'ds_agent.infrastructure.persistence.promotion_decision_store',
        'ds_agent.infrastructure.persistence.deploy_monitor_state_store',
        'ds_agent.application.ports.post_deploy_support',
        'ds_agent.application.ports.promotion_gate_support',
        'ds_agent.application.ports.review_artifact_support',
        'ds_agent.application.ports.run_diff_support',
        'ds_agent.application.services.post_deploy_usecases',
        'ds_agent.application.services.promotion_gate_usecases',
        'ds_agent.application.services.review_artifact_usecases',
        'ds_agent.application.services.run_diff_usecases',
        'ds_agent.domain.entities.experiment',
        'ds_agent.domain.entities.feature',
        'ds_agent.domain.entities.model',
        'ds_agent.domain.entities.post_deploy',
        'ds_agent.domain.entities.promotion',
        'ds_agent.domain.entities.review_artifact',
        'ds_agent.domain.entities.run_diff',
        'ds_agent.memory.semantic.application.ports',
        'ds_agent.memory.semantic.infrastructure.sqlite_base',
        'ds_agent.memory.semantic.infrastructure.sqlite_metric_repo',
        'ds_agent.runtime.post_deploy_monitor',
        # Self-improve
        'ds_agent.self_improve',
        'ds_agent.self_improve.post_project',
        'ds_agent.self_improve.pattern_learner',
        'ds_agent.self_improve.skill_extractor',
        'ds_agent.self_improve.memory_hints',
        # P1-12: artifact export infra
        'ds_agent.infrastructure.artifact',
        'ds_agent.infrastructure.artifact.exporters',
        'markdown',
        'markdown.extensions',
        'markdown.extensions.tables',
        'markdown.extensions.fenced_code',
        'markdown.extensions.sane_lists',
        'markdown.extensions.toc',
        'docx',
        'openpyxl',
        'PIL',
        'PIL.Image',
        'PIL.ImageColor',
        'PIL.ImageFile',
        # Dependencies
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'structlog',
        'yaml',
        'dotenv',
        # S-packaging-numpy (2026-04-18): backend import chain uses these at
        # module-load time via verifiers, ab_test_analyzer, tools/data_*.
        # Previously excluded, which made PyInstaller bundle fail at
        # factory.create_agent import.
        'numpy',
        'scipy',
        'scipy.stats',
        'pandas',
    ] + ML_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Kept out intentionally. RFC_2026-04_ml_deps_policy.md §3.2:
        # - DL frameworks (torch/tensorflow) are 2-4 GB each and out of Epic
        # - cv2 / tkinter unused
        # - dev tools (pytest/ruff/mypy) only needed at development time
        # NOTE: sklearn / matplotlib / xgboost / lightgbm WERE excluded before
        # 2026-04-18 under the assumption that the sandbox subprocess uses an
        # external system Python — but in frozen mode the sandbox self-reexecs
        # (RFC_2026-04_sandbox_frozen_exec.md) and therefore needs the ML
        # stack inside the bundle. They now live in ML_HIDDEN.
        'tkinter',
        'cv2',
        'torch',
        'tensorflow',
        'pytest',
        'ruff',
        'mypy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ds-agent-api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # P0-05: UPX packing triggers AV false positives (esp. Defender, AhnLab).
    # Disable for signed release builds.
    upx=False,
    console=True,  # Need console for stdout READY signal
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ds-agent-backend',
)
