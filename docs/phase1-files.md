# Phase 1 file inventory

All paths below are relative to the repository root. This is the complete source/configuration/documentation inventory for the Phase 1 change.

## Updated existing files (3)

```text
.env.example
.gitignore
README.md
```

## Created files (62)

```text
backend/.dockerignore
backend/alembic.ini
backend/app/__init__.py
backend/app/agents/__init__.py
backend/app/api/__init__.py
backend/app/api/routes.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/database/__init__.py
backend/app/database/base.py
backend/app/database/seed.py
backend/app/database/session.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/models/entities.py
backend/app/schemas/__init__.py
backend/app/schemas/dashboard.py
backend/app/schemas/events.py
backend/app/services/__init__.py
backend/app/services/agents.py
backend/app/services/events.py
backend/app/services/health.py
backend/app/workers/__init__.py
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_initial.py
backend/pyproject.toml
backend/requirements.lock
backend/tests/conftest.py
backend/tests/test_foundation.py
compose.yaml
docs/architecture.md
docs/phase1-files.md
docs/verification.md
frontend/.dockerignore
frontend/.env.example
frontend/eslint.config.mjs
frontend/next-env.d.ts
frontend/next.config.ts
frontend/package-lock.json
frontend/package.json
frontend/playwright.config.ts
frontend/postcss.config.mjs
frontend/src/app/agents/[id]/page.tsx
frontend/src/app/globals.css
frontend/src/app/layout.tsx
frontend/src/app/not-found.tsx
frontend/src/app/page.tsx
frontend/src/components/agent-detail.tsx
frontend/src/components/dashboard.tsx
frontend/src/components/ui.tsx
frontend/src/hooks/use-live-events.ts
frontend/src/hooks/use-resource.ts
frontend/src/lib/api.ts
frontend/src/lib/format.ts
frontend/src/lib/types.ts
frontend/tests/dashboard.spec.ts
frontend/tsconfig.json
infra/backend.Dockerfile
infra/frontend.Dockerfile
infra/init_env.py
infra/smoke.py
```

## Generated local artifacts (ignored)

The setup also created a private root `.env`, the backend virtual environment and Python caches/package metadata, frontend dependencies/build/type caches, browser test screenshots/results, and repository-local verification tooling. They live under `backend/.venv/`, `frontend/node_modules/`, `frontend/.next/`, `frontend/test-results/`, `.cache/`, `.tools/`, and `.verification/`, plus the standard ignored Python/TypeScript cache files. These generated dependency/data trees are not source files and should not be committed.

`.verification/services.py` is a temporary test-service launcher; its PostgreSQL data, password file, and service log stay ignored. `.tools/` contains npm, the standalone Compose validator, PostgreSQL test binaries, and Redis build files used because this machine did not have Docker or system Node/npm. None is required after installing the documented prerequisites.

