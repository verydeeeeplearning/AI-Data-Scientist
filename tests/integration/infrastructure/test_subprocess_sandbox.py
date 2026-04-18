"""Integration tests: ProcessSandbox + runtime preamble enforcement.

These tests spawn real Python subprocesses and exercise the sandbox end-to-end:
- workspace writes succeed
- writes outside workspace are blocked at runtime (even if static checker misses)
- os.system is blocked at runtime
- timeouts fire
- pandas/matplotlib stay functional
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.domain.entities.sandbox import SandboxPolicy, ViolationKind
from ds_agent.infrastructure.sandbox.preamble import build_preamble, parse_violations
from ds_agent.tools.code_security import CodeSecurityChecker
from ds_agent.tools.sandbox import ProcessSandbox


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def _sandbox(
    workspace: Path,
    *,
    data_dirs: tuple[Path, ...] = (),
    timeout: int = 30,
) -> ProcessSandbox:
    policy = SandboxPolicy(
        workspace_dir=workspace,
        data_dirs=data_dirs,
        timeout_seconds=timeout,
    )
    return ProcessSandbox(
        timeout=timeout,
        working_dir=str(workspace),
        security_checker=CodeSecurityChecker(workspace_dir=workspace),
        runtime_policy=policy,
    )


@pytest.mark.integration
class TestWorkspaceIsolation:
    async def test_simple_print(self, workspace: Path):
        sb = _sandbox(workspace)
        r = await sb.execute("print('hello')")
        assert r.success
        assert r.stdout == "hello"
        assert r.violations == ()

    async def test_write_inside_workspace_succeeds(self, workspace: Path):
        sb = _sandbox(workspace)
        target = workspace / "out.csv"
        r = await sb.execute(f"open(r'{target}', 'w').write('a,b\\n1,2')")
        assert r.success
        assert target.exists()
        assert not r.violations

    async def test_write_outside_workspace_blocked(self, workspace: Path, tmp_path: Path):
        sb = _sandbox(workspace)
        outside = tmp_path / "leak.txt"
        # Bypass static checker by using obfuscation — runtime preamble must still catch it.
        code = (
            f"p = r'{outside}'\n"
            "try:\n"
            "    open(p, 'w').write('bad')\n"
            "    print('WROTE')\n"
            "except PermissionError as e:\n"
            "    print('BLOCKED')\n"
        )
        r = await sb.execute(code)
        assert "BLOCKED" in r.stdout
        assert outside.exists() is False
        kinds = {v.kind for v in r.violations}
        assert ViolationKind.FILESYSTEM in kinds
        assert any(v.blocked for v in r.violations)

    async def test_data_dir_read_allowed(self, workspace: Path, tmp_path: Path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        sb = _sandbox(workspace, data_dirs=(data,))
        r = await sb.execute(
            f"print(open(r'{data/'sample.csv'}', 'r').read())"
        )
        assert r.success, r.stderr
        assert "1,2" in r.stdout

    async def test_data_dir_write_blocked(self, workspace: Path, tmp_path: Path):
        data = tmp_path / "data"
        data.mkdir()
        sb = _sandbox(workspace, data_dirs=(data,))
        target = data / "poison.csv"
        code = (
            f"try:\n    open(r'{target}', 'w').write('x')\n    print('WROTE')\n"
            "except PermissionError:\n    print('BLOCKED')\n"
        )
        r = await sb.execute(code)
        assert "BLOCKED" in r.stdout
        assert not target.exists()


@pytest.mark.integration
class TestSubprocessBlocking:
    async def test_os_system_blocked_at_runtime(self, workspace: Path):
        sb = _sandbox(workspace)
        # Static checker also catches this, but the runtime layer is the
        # defence-in-depth behaviour we care about.
        code = (
            "try:\n"
            "    import os\n"
            "    os.system('echo hello')\n"
            "    print('RAN')\n"
            "except PermissionError:\n"
            "    print('BLOCKED')\n"
        )
        r = await sb.execute(code)
        # The static checker short-circuits first; allow either path.
        if "BLOCKED" in r.stdout:
            assert any(v.kind == ViolationKind.SUBPROCESS for v in r.violations)
        else:
            assert r.success is False
            assert "Security check failed" in r.stderr or r.return_code == -2

    async def test_os_remove_outside_workspace_blocked(self, workspace: Path, tmp_path: Path):
        # os.remove is caught by static checker (os.remove pattern).
        # Verify the static layer reports failure.
        sb = _sandbox(workspace)
        outside = tmp_path / "victim.txt"
        outside.write_text("x")
        code = f"import os\nos.remove(r'{outside}')\nprint('removed')"
        r = await sb.execute(code)
        assert r.success is False
        assert outside.exists(), "file outside workspace must not be deleted"


@pytest.mark.integration
class TestResourceLimits:
    async def test_timeout_enforced(self, workspace: Path):
        sb = _sandbox(workspace, timeout=2)
        r = await sb.execute("import time\nwhile True:\n    time.sleep(0.1)")
        assert r.success is False
        assert r.return_code == -1
        assert "timed out" in r.stderr.lower() or "timeout" in r.stderr.lower()

    async def test_memory_limit_blocks_large_alloc(self, workspace: Path):
        # Cap at 256 MB; Python startup uses ~80 MB VAS so the cap fires
        # well before a 1 GB allocation can succeed.
        policy = SandboxPolicy(
            workspace_dir=workspace,
            timeout_seconds=15,
            max_memory_mb=256,
        )
        sb = ProcessSandbox(
            timeout=15,
            working_dir=str(workspace),
            security_checker=CodeSecurityChecker(workspace_dir=workspace),
            runtime_policy=policy,
        )
        code = (
            "try:\n"
            "    big = bytearray(1024 * 1024 * 1024)\n"  # 1 GB
            "    print('ALLOCATED', len(big))\n"
            "except (MemoryError, OSError) as e:\n"
            "    print('CAPPED')\n"
        )
        r = await sb.execute(code)
        assert "CAPPED" in r.stdout, (
            f"memory cap did not fire: stdout={r.stdout!r} stderr={r.stderr!r}"
        )

    async def test_memory_limit_setup_failure_is_non_blocking(self, workspace: Path):
        # max_memory_mb=0 disables the cap entirely — verifies the disabled
        # path doesn't emit a violation and doesn't break execution.
        policy = SandboxPolicy(
            workspace_dir=workspace,
            timeout_seconds=10,
            max_memory_mb=0,
        )
        sb = ProcessSandbox(
            timeout=10,
            working_dir=str(workspace),
            security_checker=CodeSecurityChecker(workspace_dir=workspace),
            runtime_policy=policy,
        )
        r = await sb.execute("print('ok')")
        assert r.success
        assert all(v.kind != ViolationKind.RESOURCE for v in r.violations)


@pytest.mark.integration
class TestMLCompatibility:
    async def test_pandas_read_write_cycle(self, workspace: Path, tmp_path: Path):
        pd = pytest.importorskip("pandas")
        data = tmp_path / "data"
        data.mkdir()
        src = data / "input.csv"
        src.write_text("a,b\n1,2\n3,4\n5,6\n", encoding="utf-8")
        sb = _sandbox(workspace, data_dirs=(data,))
        code = (
            "import pandas as pd\n"
            f"df = pd.read_csv(r'{src}')\n"
            "print('shape=', df.shape)\n"
            f"df.to_csv(r'{workspace/'out.csv'}', index=False)\n"
        )
        r = await sb.execute(code)
        assert r.success, f"pandas cycle failed: stderr={r.stderr!r}"
        assert "(3, 2)" in r.stdout
        assert (workspace / "out.csv").exists()
        # Load back and verify
        loaded = pd.read_csv(workspace / "out.csv")
        assert loaded.shape == (3, 2)


@pytest.mark.integration
class TestPreambleParsing:
    def test_parse_violations_extracts_and_cleans(self):
        from ds_agent.infrastructure.sandbox.preamble import (
            VIOLATION_PREFIX,
            VIOLATION_SUFFIX,
        )

        stderr = (
            "Traceback line 1\n"
            + VIOLATION_PREFIX
            + '{"kind": "filesystem", "detail": "x", "blocked": true}'
            + VIOLATION_SUFFIX
            + "\nsome other error\n"
        )
        violations, cleaned = parse_violations(stderr)
        assert len(violations) == 1
        assert violations[0].kind == ViolationKind.FILESYSTEM
        assert violations[0].blocked is True
        assert "Traceback" in cleaned
        assert VIOLATION_PREFIX not in cleaned

    def test_parse_violations_handles_empty(self):
        violations, cleaned = parse_violations("")
        assert violations == ()
        assert cleaned == ""

    def test_build_preamble_roundtrip(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        policy = SandboxPolicy(workspace_dir=ws)
        code = build_preamble(policy, "x = {'a': 1}\nprint(x)")
        # Must contain both preamble markers and original code
        assert "_SANDBOX_POLICY" not in code  # policy is loaded via _POLICY
        assert "_POLICY" in code
        assert "x = {'a': 1}" in code
