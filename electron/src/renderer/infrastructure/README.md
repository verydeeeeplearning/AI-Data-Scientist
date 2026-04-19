# Infrastructure Layer (renderer)

Adapters that implement application-layer port interfaces.

Houses:
- `api/` — HTTP/WS RPC clients
- `ws/` — WebSocket subscribers + envelope schemas (PLAN_03)
- `ipc/` — Electron IPC adapters
- `storage/` — localStorage / sessionStorage adapters

May import any external library and is the only layer permitted to do so
for I/O. Components import infrastructure indirectly (via hooks that
combine stores + use cases).
