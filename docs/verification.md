# Phase 1 verification

Verified on this macOS ARM64 workspace using Python 3.12.14 and Node.js 24.19.0. Application dependencies are installed under `backend/.venv` and `frontend/node_modules`; exact resolved versions are recorded in `backend/requirements.lock` and `frontend/package-lock.json`.

| Check | Result |
| --- | --- |
| Backend unit/API tests | 17 passed |
| Backend lint | Ruff passed |
| Migration upgrade, downgrade, re-upgrade | Passed on isolated SQLite test databases |
| PostgreSQL 17 migration and model parity | `alembic upgrade head` and `alembic check` passed |
| Development seed, run twice | Exactly Agent A/equities and Agent B/options, $1,000 each, no duplicate agents |
| Seed preservation and configurable balances | Passed in tests; existing balance/status are preserved |
| Live `/health` | HTTP 200; backend, PostgreSQL, and Redis healthy |
| REST integration | Both agent summaries, details, and empty trade-history endpoints passed |
| Live SSE stream | Received valid `heartbeat` envelope over HTTP |
| Frontend lint and TypeScript | Passed |
| Production frontend build | Passed with Webpack |
| Browser integration | 3 Playwright tests passed against real API and services |
| Browser behaviors | Both detail routes, empty history, real heartbeat, mobile layout, API failure state |
| Visual review | Desktop and 390px mobile screenshots inspected; no horizontal overflow |
| Frontend dependency audit | npm reported 0 vulnerabilities at installation |
| Docker Compose configuration | Validated with Compose v2.39.4 (`config --quiet`) |
| Docker image build and stack boot | Not run: Docker engine is not installed on this Mac |

For the live checks, temporary repository-local PostgreSQL 17.10 binaries and a compiled Redis 7.4.7 instance were used, with generated credentials and loopback-only listeners. PostgreSQL schema/data live under the ignored `.verification/` directory and are separate from future Docker volumes. These services are verification tooling, not an alternative application architecture or a new required dependency. The temporary data services, API, and frontend were stopped after verification to free the development ports.

The unit suite uses disposable SQLite databases and stubs Redis health. The separate live checks use actual PostgreSQL and Redis; the browser tests do not mock agent data. The API failure test intentionally blocks its browser's agent request to verify the error state.

The environment blocked Turbopack's internal port binding even after an approved retry. Both Next.js dev/build scripts therefore select its supported Webpack path. The tested production build contains the dashboard and the dynamic UUID detail route.

The installed Starlette version emits one upstream deprecation warning for the supported `httpx` TestClient adapter. It does not affect the passing test results. The Next.js-compatible ESLint 9 package also reports an upstream support warning; it is locked and the frontend audit reported no vulnerabilities.

Test screenshots and traces are ignored under `frontend/test-results/`. Local test binaries, downloaded tools, package caches, and temporary service data are ignored under `.tools/`, `.cache/`, and `.verification/`. The generated `.env` contains only local development credentials and remains ignored. No Git commit or push was performed.
