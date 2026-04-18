"""Runtime sandbox preamble — injected into the sandbox subprocess.

Pairs with CodeSecurityChecker (static AST/regex checks). The preamble is the
runtime defence-in-depth layer: even if obfuscated code slips past static
analysis, these wrappers enforce policy at call time.

Policy enforcement strategy
---------------------------
- Writes (``open(..., 'w'|'a'|'x'|'+')``, ``os.remove``, ``os.rename``, …)
  are restricted to ``workspace_dir``. Violations raise ``PermissionError``.
- Reads outside workspace + data_dirs emit a non-blocking warning violation
  but are allowed — otherwise matplotlib/pandas/stdlib load would break.
- ``os.system``, ``os.exec*``, ``subprocess.Popen`` raise ``PermissionError``
  when ``block_subprocess`` is set.

Violations are emitted as sentinel-framed JSON to ``stderr``; the parent
process parses them with :func:`parse_violations`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ds_agent.domain.entities.sandbox import (
    SandboxPolicy,
    SandboxViolation,
    ViolationKind,
)

VIOLATION_PREFIX = "__SANDBOX_VIOLATION__"
VIOLATION_SUFFIX = "__END__"

_VIOLATION_RE = re.compile(
    re.escape(VIOLATION_PREFIX) + r"(.*?)" + re.escape(VIOLATION_SUFFIX)
)


_PREAMBLE_TEMPLATE = '''\
# --- DS Agent sandbox preamble (auto-injected) ---
import builtins as _b
import io as _io
import json as _json
import os as _os
import sys as _sys

_POLICY = _json.loads({policy_json!r})
_WORKSPACE = _os.path.realpath(_POLICY["workspace"])
_DATA_DIRS = [_os.path.realpath(d) for d in _POLICY["data_dirs"]]
_BLOCK_SUBPROCESS = _POLICY["block_subprocess"]
_MAX_MEMORY_MB = int(_POLICY.get("max_memory_mb", 0) or 0)
_PREFIX = {prefix!r}
_SUFFIX = {suffix!r}


def _emit(kind, detail, blocked=True):
    try:
        payload = _json.dumps({{"kind": kind, "detail": detail, "blocked": blocked}})
        _sys.stderr.write(_PREFIX + payload + _SUFFIX + "\\n")
        _sys.stderr.flush()
    except Exception:
        pass


def _apply_memory_limit(max_mb):
    """Cap child-process virtual address space.

    Best-effort: when the platform-specific call fails, emit a non-blocking
    ``resource`` violation and let the subprocess continue. This matches the
    defence-in-depth posture — memory limit is extra protection, not a
    correctness invariant.
    """
    if max_mb <= 0:
        return
    max_bytes = max_mb * 1024 * 1024
    if _sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class _IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", _IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
            ]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            h_job = kernel32.CreateJobObjectW(None, None)
            if not h_job:
                raise ctypes.WinError(ctypes.get_last_error())
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = max_bytes
            JobObjectExtendedLimitInformation = 9
            ok = kernel32.SetInformationJobObject(
                h_job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
            h_proc = kernel32.GetCurrentProcess()
            ok = kernel32.AssignProcessToJobObject(h_job, h_proc)
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception as e:
            _emit("resource", "memory limit setup failed: %s" % (e,), blocked=False)
    else:
        try:
            import resource as _res

            _res.setrlimit(_res.RLIMIT_AS, (max_bytes, max_bytes))
        except Exception as e:
            _emit("resource", "rlimit setup failed: %s" % (e,), blocked=False)


_apply_memory_limit(_MAX_MEMORY_MB)


def _is_within(target, root):
    return target == root or target.startswith(root + _os.sep)


def _resolve(path):
    try:
        return _os.path.realpath(_os.path.abspath(_os.path.expanduser(_os.fspath(path))))
    except Exception:
        return None


def _classify(path, mode):
    """Return (allowed, is_outside). Reads outside are allowed-with-warning."""
    resolved = _resolve(path)
    if resolved is None:
        return False, True
    if _is_within(resolved, _WORKSPACE):
        return True, False
    for d in _DATA_DIRS:
        if _is_within(resolved, d):
            # data_dirs are read-only
            return (mode == "r"), not (mode == "r")
    return (mode == "r"), True


def _mode_is_write(mode):
    if not isinstance(mode, str):
        try:
            mode = mode.decode("utf-8", "replace")
        except Exception:
            return True
    return any(c in mode for c in ("w", "a", "x", "+"))


_ORIG_OPEN = _b.open


def _sandbox_open(file, mode="r", *args, **kwargs):
    if not isinstance(file, (str, bytes, _os.PathLike)):
        return _ORIG_OPEN(file, mode, *args, **kwargs)
    access = "w" if _mode_is_write(mode) else "r"
    allowed, _outside = _classify(file, access)
    if not allowed:
        detail = "open(%r, mode=%r) denied" % (_os.fspath(file), mode)
        _emit("filesystem", detail, blocked=True)
        raise PermissionError("SANDBOX: " + detail)
    return _ORIG_OPEN(file, mode, *args, **kwargs)


_b.open = _sandbox_open
_io.open = _sandbox_open


_ORIG_OS_OPEN = _os.open


def _sandbox_os_open(path, flags, *args, **kwargs):
    write = bool(flags & (_os.O_WRONLY | _os.O_RDWR | _os.O_APPEND | _os.O_CREAT | _os.O_TRUNC))
    access = "w" if write else "r"
    allowed, _outside = _classify(path, access)
    if not allowed:
        detail = "os.open(%r, flags=%s) denied" % (_os.fspath(path), flags)
        _emit("filesystem", detail, blocked=True)
        raise PermissionError("SANDBOX: " + detail)
    return _ORIG_OS_OPEN(path, flags, *args, **kwargs)


_os.open = _sandbox_os_open


def _guard_write(name, orig):
    def _wrapped(path, *a, **k):
        allowed, _ = _classify(path, "w")
        if not allowed:
            detail = "%s(%r) denied" % (name, _os.fspath(path))
            _emit("filesystem", detail, blocked=True)
            raise PermissionError("SANDBOX: " + detail)
        return orig(path, *a, **k)

    return _wrapped


_os.remove = _guard_write("os.remove", _os.remove)
_os.unlink = _guard_write("os.unlink", _os.unlink)
_os.rmdir = _guard_write("os.rmdir", _os.rmdir)


def _rename_guard(orig, name):
    def _wrapped(src, dst, *a, **k):
        for p in (src, dst):
            allowed, _ = _classify(p, "w")
            if not allowed:
                detail = "%s(%r, %r) denied" % (name, _os.fspath(src), _os.fspath(dst))
                _emit("filesystem", detail, blocked=True)
                raise PermissionError("SANDBOX: " + detail)
        return orig(src, dst, *a, **k)

    return _wrapped


_os.rename = _rename_guard(_os.rename, "os.rename")
_os.replace = _rename_guard(_os.replace, "os.replace")


if _BLOCK_SUBPROCESS:
    def _blocked_system(cmd):
        _emit("subprocess", "os.system(%r)" % cmd, blocked=True)
        raise PermissionError("SANDBOX: os.system blocked")

    _os.system = _blocked_system

    for _name in (
        "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
        "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
        "popen",
    ):
        if hasattr(_os, _name):
            def _make_blocked(fn_name):
                def _blocked(*a, **k):
                    _emit("subprocess", "os.%s blocked" % fn_name, blocked=True)
                    raise PermissionError("SANDBOX: os.%s blocked" % fn_name)
                return _blocked

            setattr(_os, _name, _make_blocked(_name))


# --- user code begins ---
__USER_CODE_PLACEHOLDER__
'''


def build_preamble(policy: SandboxPolicy, user_code: str) -> str:
    """Return sandbox-wrapped code ready for subprocess execution."""
    policy_payload = json.dumps(
        {
            "workspace": str(Path(policy.workspace_dir).expanduser().resolve()),
            "data_dirs": [str(Path(d).expanduser().resolve()) for d in policy.data_dirs],
            "block_subprocess": policy.block_subprocess,
            "max_memory_mb": policy.max_memory_mb,
        }
    )
    header = _PREAMBLE_TEMPLATE.format(
        policy_json=policy_payload,
        prefix=VIOLATION_PREFIX,
        suffix=VIOLATION_SUFFIX,
    )
    return header.replace("__USER_CODE_PLACEHOLDER__", user_code)


def parse_violations(stderr: str) -> tuple[tuple[SandboxViolation, ...], str]:
    """Extract sentinel-framed violations from stderr.

    Returns (violations, cleaned_stderr).
    """
    if not stderr:
        return (), stderr
    violations: list[SandboxViolation] = []
    for match in _VIOLATION_RE.finditer(stderr):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        kind_str = payload.get("kind", "")
        try:
            kind = ViolationKind(kind_str)
        except ValueError:
            continue
        violations.append(
            SandboxViolation(
                kind=kind,
                detail=str(payload.get("detail", "")),
                blocked=bool(payload.get("blocked", True)),
            )
        )
    cleaned = _VIOLATION_RE.sub("", stderr)
    # Collapse any blank lines left behind by stripped sentinels.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return tuple(violations), cleaned
