# Phase 3 verification

Verified locally on macOS ARM64 using Python 3.12, Node 24, PostgreSQL 17, Redis 7.4 and installed Chrome. No real-money executor, credentialed market request or paid AI request was used. All paper trades/research/fixtures/budget simulations were isolated in `ai_farm_phase3_verify*` databases. The original `ai_farm` database received only the additive migration and idempotent seed; both original accounts remain $1,000, with zero trades and every pre-migration column preserved.

## Results

| Check | Result |
| --- | --- |
| Backend unit/API/migration suite | 123 passed, including all 73 Phase 2 tests |
| Ruff and formatting | Passed |
| Dependency consistency | No broken requirements |
| Frontend lint / types / formatting | Passed |
| Next.js production build | Passed; dashboard, agent, trade, research and Marketplace routes |
| Chrome integration suite | 7 passed |
| Fresh PostgreSQL migration to 0003 | Passed |
| Forward 0002 → 0003 migration | All old columns preserved; metadata parity passed |
| Original database | A $1,000, B $1,000, zero trades after upgrade/seed |
| Native A/B intelligence + monitoring | Both executed and closed via final RiskEngine/PaperBroker; confidence settled |
| Native concurrent budget reservations | 10 connections, 1 approved / 9 denied, $0.003 reserved, zero HTTP calls |
| API/health/Redis | Passed read-only smoke check |
| SSE | Heartbeat and live paper/research/Marketplace updates passed with polling suppressed |
| Safety | Stale data, event proximity, missing coverage, opposite analysis direction, lease loss and paper-only enforcement covered |
| No-key provider / AI disabled | Explicit mock fallback and zero AI calls covered |
| Marketplace | Idempotent fixture, $48 illustrative net, persistable outcome and N/A unknowns covered |
| UI | Desktop and 390px layouts, research/Shadow/contracts, API failure, disabled AI and rate-limit message covered |
| Compose configuration | `--profile paper config --quiet` passed |
| Docker images/boot | Pending: no Docker engine available |
| Credentialed Tradier/OpenAI | Pending: not exercised with real keys |

Initial browser attempts found missing seed setup, an overly specific N/A assertion, and a scenario-order dependency: Phase 2's price-rise demo legitimately made the mock option too expensive for a new entry. The corrected suite runs affordable research before that lifecycle and uses freshly seeded databases. No risk limit was weakened to make a test pass.

Warnings: upstream Starlette/httpx TestClient deprecation; Chrome NO_COLOR/FORCE_COLOR notice; restricted pip-cache warning. These are not failed checks. Mock returns are not performance evidence. Live calendars, price comparables, sale-time/probability models, statistically valid system rankings and an options benchmark remain unavailable. Greek timestamps without timezone are deliberately rejected for live entry. AI model IDs/price ceilings require operator verification. The app lacks authentication and data-retention controls; keep it local.

## Standard reproducible checks

From `backend/`:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests migrations scripts
.venv/bin/ruff format --check app tests migrations scripts
.venv/bin/python -m pip check
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m app.database.seed
```

From `frontend/`:

```sh
npm run lint
npm run typecheck
npm run format:check
npm run build
# Running API must share the same freshly seeded disposable DATABASE_URL as this CLI.
PAPER_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1
```

From root: `python3 infra/smoke.py` and `docker compose --profile paper config --quiet`. The seven browser tests are an ordered integration scenario; do not run the mutating tests on valuable data or rerun them without a new disposable database.

`backend/scripts/verify_phase3.py` is a committed native verification helper. Point `DATABASE_URL` at a **new empty PostgreSQL database whose name begins `ai_farm_phase3_verify`**, then from backend run `PYTHONPATH=. .venv/bin/python scripts/verify_phase3.py`. It refuses other/nonempty databases, performs forward-migration preservation, both full intelligence flows, Marketplace import, real Redis and concurrent reservation checks. It does not delete anything. Retain or remove disposable databases later at your discretion; verification itself never drops them.

## Exact startup on this existing Mac, without Docker

These commands reuse ignored tools already installed in this workspace. Fresh clones should use README's portable setup.

```sh
# Terminal 1: Ctrl-C stops both local data services.
cd /Users/ethanbailey/Documents/ai-farm
backend/.venv/bin/python .verification/services.py
```

```sh
# Terminal 2: original development DB, not verification databases.
cd /Users/ethanbailey/Documents/ai-farm/backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.database.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
# Terminal 3: dashboard.
cd /Users/ethanbailey/Documents/ai-farm/frontend
export PATH="/Users/ethanbailey/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH"
node ../.tools/npm/bin/npm-cli.js run dev
```

Open http://localhost:3000. In terminal 4:

```sh
cd /Users/ethanbailey/Documents/ai-farm/backend
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli research --demo
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli marketplace-fixture
# Optional: this writes paper trades and compounds balances; it does NOT reset them.
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli research --demo --execute
```

The existing ignored `.verification/phase3_run.py` helper can create/select isolated databases without exposing local credentials. For a new native verification run from root:

```sh
PHASE3_VERIFY_DATABASE=ai_farm_phase3_verify_new_run backend/.venv/bin/python .verification/phase3_run.py backend env PYTHONPATH=. .venv/bin/python scripts/verify_phase3.py
```

Choose a never-used name. Generated dependencies, private `.env`, service binaries, database directories, build output and screenshots remain ignored. No commit or push was made. Verification servers are stopped at handoff.
