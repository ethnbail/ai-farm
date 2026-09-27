# AI Farm

Phase 5 adds a user-controlled Marketplace workbench at `/marketplace`: manual/URL/CSV/JSON acquisition, observed price history, duplicate detection, transparent resale and sell-through analysis, travel-adjusted economics, purchase/sale recordkeeping, inventory and calibration. No scraping, seller contact, payment or purchasing automation exists. Missing market evidence stays unknown. Marketplace records never spend Agent A/B paper funds.

Start with [Phase 5 architecture and exact startup/demo commands](docs/phase5-marketplace.md), [verification](docs/phase5-verification.md), and [complete changed-file inventory](docs/phase5-files.md). Migration `0004` is additive. HTTP writes require `LOCAL_WRITES_ENABLED=true` and a trusted local Origin; defaults remain read-only. Earlier phase sections below describe the preserved system.

Phase 4 adds a live, original low-poly 3D farm to the existing paper-trading and intelligence system. Seven buildings and five animal mascots visualize backend state through one shared SSE connection. Click a building or its keyboard-accessible button for live details. The complete Phase 3 dashboard remains available through **Switch to 2D**, reduced motion, WebGL failure, or performance fallback. Agent A trades long equities/ETFs; Agent B trades long calls/puts. Their accounts remain independent; the existing RiskEngine and PaperBroker are unchanged.

Defaults are explicitly MOCK market data, disabled AI and disabled workers. A read-only Tradier adapter and optional OpenAI structured analysis can be configured backend-side; neither was called with real credentials during verification. There is no real broker or marketplace scraping/messaging/purchasing. Animations make no AI calls and cannot submit orders. Agent A and Agent B start idle with $1,000 each. Seeding never creates trades or resets balances. NO_TRADE is a valid outcome.

Start with [Phase 4 architecture and simulator](docs/phase4-3d-farm.md), [verification and exact local startup](docs/phase4-verification.md), and the [complete Phase 4 file inventory](docs/phase4-files.md). [Phase 3 intelligence](docs/phase3-intelligence.md) remains the backend reference; earlier verification documents describe their historical runs.

Public frontend settings: `NEXT_PUBLIC_ENABLE_3D_FARM=true` and `NEXT_PUBLIC_REDUCED_SCENE=false`. Set these in `frontend/.env.local` for native development or the root `.env` for Compose. Rebuild production after changing public settings. The **Reduced motion** checkbox and OS preference select the complete 2D experience. Run `npm run dev`, open `/`, and expand **DEVELOPMENT ONLY · Farm Event Simulator** to rehearse animations locally without changing balances. The simulator is excluded from production builds.

## Quick start: the whole stack in Docker

Prerequisites: Git, Python 3 (for the standard-library configuration helper), and Docker Engine with Compose v2. On macOS, install and start Docker Desktop. Ports 3000, 8000, 5432, and 6379 must be available. Node and a host Python environment are not needed for the containerized applications.

From the repository root:

```sh
python3 infra/init_env.py
docker compose up --build -d
docker compose ps -a
python3 infra/smoke.py
```

The helper creates an ignored, owner-readable `.env` with random local PostgreSQL and Redis passwords. It leaves an existing `.env` unchanged and requires no third-party API keys. Compose starts PostgreSQL and Redis, waits for PostgreSQL, runs the migration and idempotent agent seed in the `init` service, and starts the API and dashboard. `init` exiting with code 0 is expected.

- Dashboard: [http://localhost:3000](http://localhost:3000)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

Useful commands:

```sh
docker compose logs -f backend frontend
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.database.seed
docker compose exec backend python -m pytest -q -p no:cacheprovider
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
docker compose down
```

Backend code and frontend `src/` changes reload during development. Rebuild after changing dependency manifests or frontend configuration: `docker compose up --build -d`. PostgreSQL and Redis use named volumes; `docker compose down` preserves their data. Do not remove volumes unless you intend to delete that data. Generated credentials must stay consistent with an existing PostgreSQL volume; changing `.env` alone does not rotate a database password.

## Local applications, containerized data services

Additional prerequisites: Node.js 24 LTS with npm, Python 3.12 or newer with venv support. Python 3.12 is the Docker baseline. PostgreSQL 17 and Redis 7.4 can also run natively if their connection URLs are configured in `.env`.

Start the data services from the repository root:

```sh
python3 infra/init_env.py
docker compose up -d postgres redis
```

Backend, in terminal 1:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
alembic upgrade head
python -m app.database.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend reads the root `.env` automatically. Shell environment variables take precedence. The dependency lock includes development tools. When changing dependencies, update the manifest and lock together in a clean virtual environment and rerun verification.

Frontend, in terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

The frontend defaults to `http://localhost:8000`. To change that origin, copy `frontend/.env.example` to `frontend/.env.local`, then edit `NEXT_PUBLIC_API_URL` and restart the frontend. Never copy the root `.env` into the frontend. The root public API variable is passed to the frontend by Compose; native Next.js reads its own `frontend/.env.local`.

Only run one frontend/backend pair on these ports at a time. Production-mode frontend check:

```sh
cd frontend
npm run build
npm run start
```

The dev and build scripts explicitly use Next.js's supported Webpack bundler. Turbopack's internal port binding was blocked in the scaffold verification environment; this choice keeps the tested commands consistent.

## Verification

Backend tests use isolated SQLite databases created through Alembic, with no real broker or external API access. They exercise simulated fills, isolated accounting, full-premium options risk, stops/targets, expiration, market hours, atomic rollback, events, migrations, and performance. Redis is stubbed in unit tests; separate integration verification uses actual PostgreSQL and Redis. Development seed data contains no trades.

```sh
cd backend
source .venv/bin/activate
python -m pytest -q
ruff check app tests migrations
alembic check
```

`alembic check` requires a running, migrated PostgreSQL database and confirms that models match the schema. Generate future migrations with `alembic revision --autogenerate -m "describe change"`, review the generated file, then run `alembic upgrade head`.

Frontend checks:

```sh
cd frontend
npm run lint
npm run typecheck
npm run build
```

With the full stack running and freshly seeded default balances, browser integration tests retrieve real agents, open both detail pages, receive a heartbeat, check mobile overflow, and verify the API failure state:

```sh
cd frontend
npx playwright install chromium
npm run test:e2e
```

Alternatively, with Google Chrome installed: `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e`. The suite expects freshly seeded $1,000 accounts, no trades and no research. Two opt-in tests write paper trades, research and Marketplace fixtures: use a disposable database and run `PAPER_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1`. The running API and CLI must use the same database. Tests disable polling to prove SSE refresh, and require `backend/.venv/bin/python` plus Redis. A second run needs a new database; tests never reset data. Provider failure and AI-disabled states are also covered.

From the root, `python3 infra/smoke.py` verifies HTTP health, real PostgreSQL/Redis connectivity, both agents, detail/trade endpoints, and one SSE heartbeat. To inspect the stream directly:

```sh
curl -N http://localhost:8000/api/events
```

## Structure and architecture

```text
frontend/       Next.js App Router, TypeScript, Tailwind, browser integration tests
backend/
  app/
    api/        Read APIs, gated local watchlist writes, SSE transport
    core/       Validated backend-only settings
    database/   SQLAlchemy sessions and explicit development seeding
    models/     Agents, portfolios, orders, fills, positions, trades, events, benchmarks
    schemas/    Pydantic response and event contracts
    services/   Research, AI/budgets, Shadow, events, Marketplace, risk, accounting
    market_data/ Normalized providers, read-only Tradier, deterministic mock fixtures
    agents/     Transparent equity/options strategy proposals
    workers/    Redis-coordinated scheduler and explicit development demo CLI
  migrations/   Versioned Alembic schema
  tests/        API, migration, seed, input, and failure checks
infra/          Dockerfiles, configuration helper, smoke check
docs/           Architecture, verification results, exact file inventory
compose.yaml    Local development stack
```

The browser reads FastAPI and shares one `/api/events` EventSource across pages. Business events refresh data immediately; 15-second polling remains a fallback. Heartbeats default to 5 seconds. PostgreSQL owns durable records and ordered, replayable business events; Redis provides worker leases and job deadlines, not event storage. Decimal/Numeric handles all accounting; frontend numbers are display-only.

See [trading architecture](docs/trading-engine.md), [risk controls](docs/risk-engine.md), [paper fills](docs/paper-broker.md), [market data](docs/market-data.md), [Phase 2 verification](docs/phase2-verification.md), and [changed files](docs/phase2-files.md). Phase 1 documents remain historical references.

## Run the deterministic paper simulation

With PostgreSQL/Redis running and the backend environment installed, from the root:

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.database.seed
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage entry
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage mark
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --stage exit --outcome target
```

Keep the dashboard open to watch each stage. For a complete stop-loss scenario after the first run has closed:

```sh
ENABLE_DEVELOPMENT_ACTIONS=true .venv/bin/python -m app.workers.cli demo --outcome stop
```

These commands persist paper trades and compound existing balances; **they do not reset accounts**. Stop the scheduled worker before staged demos. The demo clock is fixed at September 24, 2026, 14:00 UTC, independent of actual market hours. Old simulation timestamps are correctly marked STALE relative to wall-clock time in the UI; replay retains the original MOCK source. On a fresh $1,000 account, the target demo finishes at $1,005.88 for A and $1,010.59 for B. The fictional FARM option is small enough for the full-premium risk cap; the SPY option is rejected, not force-sized.

For Docker, use `docker compose exec -e ENABLE_DEVELOPMENT_ACTIONS=true backend python -m app.workers.cli demo`. For scheduled paper trading, opt in explicitly:

```sh
# Native, from backend/ (uses actual exchange hours):
PAPER_WORKER_ENABLED=true .venv/bin/python -m app.workers.scheduler
# Or, from root, the optional Compose profile:
docker compose --profile paper up --build -d
```

Do not run a native worker and the Compose worker together. The worker uses deterministic cycling MOCK fixtures, not a profitable trading system. Stop the native process with Ctrl-C or the container with `docker compose --profile paper stop paper-worker`.

## Configuration and boundaries

- `.env` and local artifacts are ignored. `.env.example` contains placeholders only.
- Starting balances are configured with `AGENT_A_STARTING_BALANCE` and `AGENT_B_STARTING_BALANCE` before first seeding. Reseeding never overwrites existing agents.
- Existing `.env` files need not be overwritten. See `.env.example` for controls. `TRADING_MODE` other than `paper` fails closed. `MARKET_DATA_PROVIDER` accepts `mock` or `tradier`; missing Tradier credentials explicitly use MOCK. A configured provider failure blocks new trades, never silently substitutes fake live prices.
- `CORS_ORIGINS` is a JSON array of allowed origins. Defaults cover localhost and 127.0.0.1 on port 3000. Wildcard origins are rejected.
- Keys remain backend-only. AI requires explicit enablement, key, priced model slots and both budgets. Blank budgets allow no paid calls. Disabled AI continues deterministic research with zero usage. Read [AI budget enforcement](docs/ai-budget.md) before enabling; model prices must be verified. Discord remains unused.
- `/health` returns 200 when both database and Redis checks pass, or 503 with explicit component statuses. The heartbeat only proves stream connectivity; it does not claim the agents are running or the database is healthy.
- All Compose ports bind to loopback. There is no authentication yet: this stack is for a trusted local development machine, not public deployment.

## Deferred work

Real execution, verified live calendar integration, sophisticated option pricing, full historical replay, automatic marketplace collection, editable ZIP/radius, authentication, adaptive training and the 3D farm remain future work. Commissions, taxes, corporate actions, exchange depth, physical exercise/delivery and assignment are not modeled. Options expire via documented synthetic cash settlement. Marketplace price ranges are supplied estimates; sale time/probability and statistically unsupported reliability stay N/A. Data and AI adapters still need credentialed integration verification. Docker build/boot is pending where an engine is available.

The same service boundaries can run on a Proxmox Linux VM. Before remote deployment, use production process commands, production images without development mounts/reload, a TLS reverse proxy with SSE buffering disabled, authentication, managed secrets, backups, monitoring, and explicit remote CORS/API origins. Those deployment changes are not implemented in Phase 1.

Suggested commit message: `feat: add Phase 3 paper-only intelligence and research layer`
