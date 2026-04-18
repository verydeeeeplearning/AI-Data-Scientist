"""Packaged smoke tests — exercise the built backend binary, not source.

These tests run against the PyInstaller-built ``ds-agent-api`` executable to
catch packaging regressions (missing modules, bad asset paths, DLL conflicts)
that source-level pytest cannot.

Run with: ``pytest tests/smoke -m smoke``
Provide the binary path via ``PACKAGED_BINARY_PATH`` env var, or rely on the
default ``dist/ds-agent-backend/ds-agent-api.exe`` (built by ``scripts/build_backend.py``).
"""
