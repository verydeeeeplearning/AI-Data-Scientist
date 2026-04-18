# Packaged Smoke Tests

These tests exercise the **PyInstaller-built backend binary**, not the Python
source. They catch packaging regressions that source-level pytest cannot:

- Missing PyInstaller hidden imports
- Bad data file paths after bundling
- Native DLL conflicts at launch
- Broken `READY:` handshake with the Electron host

## Run locally

```bash
# 1. Build the binary (or skip if dist/ds-agent-backend/ already exists)
python scripts/build_backend.py --clean

# 2. Run the suite
python -m pytest tests/smoke -v -m smoke

# Or use the runner that does both
python scripts/run_smoke.py --build
```

## Configuration

| Env var | Purpose |
|---------|---------|
| `PACKAGED_BINARY_PATH` | Override binary path (default: `dist/ds-agent-backend/ds-agent-api[.exe]`) |
| `DS_AGENT_WS_TOKEN` | Forced to `smoke-token` by the fixture so WS endpoint is deterministic |

## When binary is missing

`tests/smoke/conftest.py::packaged_binary` calls `pytest.skip()` rather than
failing — so a developer running `pytest` locally without a packaged build
will see "skipped" instead of red. CI builds the binary first so the suite
actually executes.

## CI

`.github/workflows/smoke.yml` runs this suite on every PR/main push using a
Windows runner. macOS/Linux runners can be added once their PyInstaller specs
are validated (currently the spec targets Windows binary layout).

## Related

- `REGRESSION_MATRIX.md` — full critical-user-journey checklist.
- `Docs/productization/P0_06_packaged_qa_smoke_tests.md` — design doc.
