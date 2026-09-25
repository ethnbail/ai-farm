# AI Farm

Phase 1 is a working, read-only foundation for two paper trading agents and a future local resale agent. It includes a warm 2D dashboard, agent details, PostgreSQL persistence, migrations, development seeding, service health, and a live SSE heartbeat.

No trading strategies, order execution, brokerage integrations, marketplace scraping, paid AI calls, or 3D world are implemented. Agent A and Agent B start idle with $1,000 in paper funds each. Development seeding never creates trades or resets existing balances.

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

Backend tests are isolated SQLite databases created through Alembic, with no broker or external API access. Redis health is stubbed in unit tests; the smoke test checks the real services. Unit fixtures contain synthetic trade rows solely to test calculations; development seed data contains no trades.

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

Alternatively, with Google Chrome installed: `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e`. Browser tests expect the default $1,000 balances and no trades; use a fresh development database. They do not modify backend data.

From the root, `python3 infra/smoke.py` verifies HTTP health, real PostgreSQL/Redis connectivity, both agents, detail/trade endpoints, and one SSE heartbeat. To inspect the stream directly:

```sh
curl -N http://localhost:8000/api/events
```

## Structure and architecture

```text
frontend/       Next.js App Router, TypeScript, Tailwind, browser integration tests
backend/
  app/
    api/        Read-only routes and SSE transport
    core/       Validated backend-only settings
    database/   SQLAlchemy sessions and explicit development seeding
    models/     Agent, Trade, MarketplaceOpportunity, SystemEvent
    schemas/    Pydantic response and event contracts
    services/   Agent summaries, health checks, heartbeat generation
    agents/     Reserved module; no strategies or execution
    workers/    Reserved module; no background jobs
  migrations/   Versioned Alembic schema
  tests/        API, migration, seed, input, and failure checks
infra/          Dockerfiles, configuration helper, smoke check
docs/           Architecture, verification results, exact file inventory
compose.yaml    Local development stack
```

The browser reads the FastAPI API and subscribes to `/api/events` with `EventSource`. API data refreshes every 15 seconds; the heartbeat defaults to every 5 seconds. PostgreSQL owns durable records. Redis is running and health-checked but does not yet transport events or execute jobs. Exact balances and prices use Decimal/Numeric; API decimal values are strings, with frontend conversion only for display.

See [architecture](docs/architecture.md), [verification results](docs/verification.md), and the [complete file inventory](docs/phase1-files.md).

## Configuration and boundaries

- `.env` and local artifacts are ignored. `.env.example` contains placeholders only.
- Starting balances are configured with `AGENT_A_STARTING_BALANCE` and `AGENT_B_STARTING_BALANCE` before first seeding. Reseeding never overwrites existing agents.
- `CORS_ORIGINS` is a JSON array of allowed origins. Defaults cover localhost and 127.0.0.1 on port 3000. Wildcard origins are rejected.
- `OPENAI_API_KEY`, `MARKET_DATA_API_KEY`, and `DISCORD_WEBHOOK_URL` are backend-only, optional, and unused. `AI_MONTHLY_BUDGET_USD` may be blank; the UI shows an unconfigured budget and usage placeholders.
- `/health` returns 200 when both database and Redis checks pass, or 503 with explicit component statuses. The heartbeat only proves stream connectivity; it does not claim the agents are running or the database is healthy.
- All Compose ports bind to loopback. There is no authentication yet: this stack is for a trusted local development machine, not public deployment.

## Deferred work

Real agent execution (including paper-trade simulation), options contract details, risk controls, market data, brokerage connections, marketplace collection and scoring, editable ZIP/radius, AI metering, persistent business-event delivery/replay, authentication, and the 3D farm remain future work. Empty trade history, inactive marketplace setup, and AI usage placeholders are intentional.

The same service boundaries can run on a Proxmox Linux VM. Before remote deployment, use production process commands, production images without development mounts/reload, a TLS reverse proxy with SSE buffering disabled, authentication, managed secrets, backups, monitoring, and explicit remote CORS/API origins. Those deployment changes are not implemented in Phase 1.

Suggested commit message: `feat: scaffold AI Farm phase 1 dashboard and backend`
