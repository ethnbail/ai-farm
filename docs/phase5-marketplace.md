# Phase 5: Marketplace workbench

The workbench is research and recordkeeping, not an execution agent. Users supply observations, validate authenticity, contact sellers, negotiate, purchase, collect and resell themselves. Marketplace accounting is separate from both paper portfolios. No external acquisition credentials or AI calls are required.

## Architecture

`MarketplaceSourceConnector` → validated `ListingInput` → existing `MarketplaceListing` → observed prices/evidence → deterministic analysis → persisted analysis/notifications → existing durable SSE → shared frontend store and farm.

`app/marketplace/connectors.py` isolates acquisition; `analysis.py` contains named pure services; `pipeline.py` owns transactions, evidence and outcomes; `api/marketplace.py` exposes local HTTP workflows. Existing Phase 3 models and opportunity endpoints remain compatible. Nine additive tables hold settings, history, duplicate matches, seller profiles, comps, demand snapshots, inventory, calibration and notifications. Migration `0004` backfills old listing dates and an initial observed price without inventing publication dates.

Routes: `/marketplace`, `/marketplace/new`, `/marketplace/import`, `/marketplace/settings`, `/marketplace/[id]`, `/marketplace/inventory`, `/marketplace/calibration`. Detail exposes evidence, history, risk, equations, manual actions and completed transaction records.

## Exact local startup

From the repository root, with Python 3.12+, Node/npm and Docker installed (or already-running native PostgreSQL/Redis):

```sh
python3 infra/init_env.py
docker compose up -d postgres redis
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
alembic upgrade head
python -m app.database.seed
LOCAL_WRITES_ENABLED=true AI_ENABLED=false PAPER_WORKER_ENABLED=false python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal from the root:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://localhost:3000/marketplace>. Root `.env` stays backend-only; never put credentials in frontend variables. Only one API/frontend pair may bind these ports. If native data services already occupy 5432/6379, skip Docker startup. `LOCAL_WRITES_ENABLED` also enables the existing local watchlist editing; Origin checking is not production authentication. Keep this server local.

## Imports and demo

From `backend/` with its virtual environment active:

```sh
python -m app.marketplace.cli import-json --file ../docs/examples/marketplace-listings.json
python -m app.marketplace.cli import-csv --file ../docs/examples/marketplace-listings.csv
# Explicitly persist an inspected import:
python -m app.marketplace.cli import-json --file ../docs/examples/marketplace-listings.json --apply
# Fictional demo: use a disposable database, never mix examples with real records.
ENABLE_DEVELOPMENT_ACTIONS=true python -m app.marketplace.cli fixture --apply
python -m app.marketplace.cli refresh-inventory --apply
```

Without `--apply`, imports run validation/analysis inside a rolled-back transaction, including events. Templates are placeholders, not real sales evidence. Configure `DATABASE_URL` privately to select a disposable database before demo writes. CLI is an explicit local administrative action; unlike HTTP, it does not require an Origin or the HTTP writes flag.

For browser imports choose CSV/JSON, paste data or select a file, leave Dry run checked first, inspect row errors, then uncheck it to save. URL import retains a session-local reference and asks for details: it does not extract or store a complete listing until submission.

## Farm event replay

For visual-only rehearsal run `npm run dev`, open `/`, expand **DEVELOPMENT ONLY · Farm Event Simulator**, click named Marketplace event buttons and use **Reset rehearsal**. It changes no backend records and makes no AI calls. Production builds exclude this simulator.

For real SSE, run the API with both `ENABLE_DEVELOPMENT_ACTIONS=true` and `LOCAL_WRITES_ENABLED=true` against a disposable database, keep `/` open, then:

```sh
curl -X POST -H 'Origin: http://localhost:3000' http://127.0.0.1:8000/api/marketplace/dev/fixture
curl -N http://127.0.0.1:8000/api/events
```

The fixture response gives listing IDs. With one fixture ID substituted:

```sh
curl -X POST -H 'Origin: http://localhost:3000' -H 'Content-Type: application/json' --data '{"listing_id":"REPLACE_WITH_FIXTURE_UUID"}' http://127.0.0.1:8000/api/marketplace/dev/price-drop
curl -X POST -H 'Origin: http://localhost:3000' -H 'Content-Type: application/json' --data '{"listing_id":"REPLACE_WITH_FIXTURE_UUID"}' http://127.0.0.1:8000/api/marketplace/dev/sale
```

Demo price/sale endpoints refuse non-fixture records. Live events use the one existing shared EventSource, not another per panel. Imported/opportunity/strong/analysis/price-drop events → ANALYZING; duplicates/aging → WAITING; passed → IDLE; bought → TRADE_ACTIVE; sold → SUCCESS. Parcels arrive at the stall, strong candidates glow, price tags flip, purchased parcels move toward inventory, passed/sold parcels leave, and aging inventory is highlighted. The 2D dashboard remains usable.

## Boundaries

USD only; no automatic geocoding, source refresh, external sold-data feed, vision analysis, AI enrichment or autonomous retraining. Browser-assisted capture means user-pasted selected fields, not a browser extension or session access. API adapters are interfaces only until approved integrations exist. Analysis reads update freshness without emitting write events; inventory aging notifications require explicit refresh. Ranking is bounded to the most recent 2,000 records, not production-scale search. Legacy outcomes remain stored but are not automatically reinterpreted as Phase 5 inventory.

See [connectors](marketplace-connectors.md), [scoring](marketplace-scoring.md), [valuation](marketplace-valuation.md), [sell-through](marketplace-sell-through.md), [risk](marketplace-risk.md), [outcomes](marketplace-outcomes.md), [calibration](marketplace-calibration.md), and [inventory](marketplace-inventory.md).
