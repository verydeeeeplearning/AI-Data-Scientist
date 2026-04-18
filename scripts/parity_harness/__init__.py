"""C13 Phase 3 — Process-level 3-Tier Interface Parity Harness.

Phase 3 upgrade of the Round 1 fallback harness. Exercises the three
channels (CLI, Telegram, Electron) at the **process** layer rather than
the factory-call layer:

  - CLI:      subprocess launch of ``ds-agent-api.exe`` + WebSocket chat
  - Telegram: in-process fake-update against TelegramRunner stubs
              (python-telegram-bot not available → documented fallback)
  - Electron: Playwright launch of packaged Electron + same backend bin

All channels use the bundled ``_NoApiKeyProvider`` canned response so no
real LLM call is issued (API key intentionally absent).

See ``harness_cli.py``, ``harness_telegram.py``, ``harness_electron.py``.
"""
