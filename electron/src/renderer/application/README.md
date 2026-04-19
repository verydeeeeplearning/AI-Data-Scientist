# Application Layer (renderer)

Use cases, DTOs, and port interfaces. Orchestrates data flow between
domain and infrastructure via abstractions.

**Constraints (enforced by `scripts/lint-arch.mjs`):**
- No `react`, `react-dom` imports (use cases must be UI-framework agnostic)
- No imports from `infrastructure/`, `components/`, `hooks/`
- May import from `domain/`
- May import generic stdlib utilities (e.g., DOM APIs for accessibility utilities)

Each use case is a single responsibility, named with a verb prefix
(e.g., `getMissionContext`, `pinArtifact`).
