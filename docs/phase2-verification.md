# Phase 2 verification

Verified on the existing macOS ARM64 workspace with Python3.12.14, Node24.19.0, PostgreSQL17.10, Redis7.4.7 and installed Google Chrome. The original development database was upgraded from0001 to0002 without changing either $1,000 balance or creating trades. All trading integration runs used separate `ai_farm_phase2_verify*` databases; their records remain under the ignored local PostgreSQL data directory for inspection.

| Check | Final result |
| --- | --- |
| Backend unit/API/migration suite | **73 passed** |
| Ruff lint and format checks | Passed, 45 Python files formatted |
| Dependency consistency | `pip check`: no broken requirements |
| Frontend ESLint / TypeScript / formatting | Passed |
| Production Next.js build | Passed with Webpack; dashboard, agents and trades routes |
| Playwright, actual production frontend/API | **4 passed**, including opt-in trading lifecycle |
| Fresh PostgreSQL migration | Passed through0002; `alembic check` found no drift |
| PostgreSQL forward migration | Preserved every original column of legacy agents, trades and events; preserved a non-default $1,100 account |
| Actual development DB upgrade/seed | Both portfolios and agents remain $1,000, distinct IDs, zero trades |
| Simultaneous PostgreSQL idempotent orders | Two concurrent requests, one trade and one fill |
| Real Redis | PING, lease exclusion and job-deadline deduplication passed |
| HTTP health | 200; backend, PostgreSQL and Redis healthy |
| REST integration | Agents, portfolios, positions, performance, history, replay, activity, market status passed |
| SSE | Immediate heartbeat, live business updates, next-sequence Last-Event-ID replay passed |
| Live dashboard | Both positions/marks/exits updated with polling disabled; details and recorded Greeks rendered |
| Mobile and failure states | 390px layouts fit; empty states and unavailable backend shown without fake balances |
| Visual inspection | Desktop/dashboard and mobile option position/replay screenshots inspected |
| Golden target lifecycle | A +$5.88 → $1,005.88; B +$10.59 → $1,010.59; independent API fill/cash equations confirmed |
| Golden stop lifecycle | A −$6.12; B −$8.71, unit tests and native PostgreSQL |
| Extra safety/accounting | Partial exits, no borrowing/shorts, full-premium options risk, expiration, rollback, stale marks, sample-size N/A passed |
| Non-paper mode | Explicit error and log; no execution |
| Compose configuration | `--profile paper config --quiet` passed |
| Git whitespace | `git diff --check` passed |
| Docker image build and boot | **Not run: Docker engine unavailable** |

Initial failing expectations were corrected after checking four-decimal fill versus cent-rounded cash accounting and compounded position sizing. All final suites pass. The upstream Starlette/httpx TestClient deprecation warning remains; it is not a test failure. Chrome tooling emitted a NO_COLOR/FORCE_COLOR warning. No new dependency upgrade was made just to silence these warnings. Full Docker image build, startup health sequencing and container worker behavior still need a later Docker-enabled check.

Fixed mock prices, option premiums/Greeks, simplified fills, synthetic expiration settlement and an unavailable options benchmark are intentional. There is no AI or real broker. Quotes are not live market observations and simulated returns are not evidence of profitability. Fees, taxes, corporate actions and physical exercise are not modeled. SSE events and snapshots have no retention policy yet. Do not expose this unauthenticated local-development application publicly.

## Reproduce the standard checks

From `backend/` with its venv installed:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests migrations
.venv/bin/ruff format --check app tests migrations
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m app.database.seed
```

From `frontend/` with Node/npm installed:

```sh
npm run lint
npm run typecheck
npm run format:check
npm run build
# API and frontend running, fresh disposable DB; this test writes paper trades:
PAPER_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1
```

Run `python3 infra/smoke.py` from root for read-only HTTP checks. Browser test API, backend CLI and its DATABASE_URL must point to the same disposable database. Do not run the opt-in lifecycle test on valuable development history. Local verification helpers and artifacts in `.verification/`, `.tools/` and `frontend/test-results/` are ignored and not application source. No commit or push was performed. Temporary API/frontend/data-service processes are stopped at handoff.

## Exact commands for this existing Mac (no Docker)

These reuse already installed, ignored Phase1 local tools; fresh clones should use the portable README setup instead. Run from `/Users/ethanbailey/Documents/ai-farm`. Use three terminals:

```sh
# Terminal 1: repository-local PostgreSQL and Redis; Ctrl-C stops both.
cd /Users/ethanbailey/Documents/ai-farm
backend/.venv/bin/python .verification/services.py
```

```sh
# Terminal 2: normal development database, not the test databases.
cd /Users/ethanbailey/Documents/ai-farm/backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.database.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
# Terminal 3: existing bundled Node/npm installation.
cd /Users/ethanbailey/Documents/ai-farm/frontend
export PATH="/Users/ethanbailey/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH"
node ../.tools/npm/bin/npm-cli.js run dev
```

Open [the dashboard](http://localhost:3000). In a fourth terminal, run a staged simulation:

```sh
cd /Users/ethanbailey/Documents/ai-farm/backend
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage entry
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage mark
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage exit --outcome target
# A subsequent full losing scenario (compounds existing balances):
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --outcome stop
```

The worker should be stopped during manual demos. For scheduled paper work instead, from backend run `PAPER_WORKER_ENABLED=true .venv/bin/python -m app.workers.scheduler`. It respects the actual exchange clock. Demo runs use a fixed simulation clock; older demo marks display STALE relative to actual time, while the entry replay remains clearly MOCK.
