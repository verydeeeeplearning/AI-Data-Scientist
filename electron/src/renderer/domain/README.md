# Domain Layer (renderer)

Pure TypeScript types, value objects, and validation logic.

**Constraints (enforced by `scripts/lint-arch.mjs` — see ADR-0006):**
- No `react`, `react-dom`, `zustand`, `axios`, or other framework imports
- No imports from `application/`, `infrastructure/`, `components/`, `hooks/`, `stores/`
- Only stdlib + intra-domain relative imports

This layer changes only when business rules change.
