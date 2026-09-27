# Phase 5 verification — 2026-09-27

## Results

- Backend: **166 passed**, including all 123 prior-phase tests and 43 Marketplace cases (parameterized cases counted individually). Ruff lint and formatting pass.
- Frontend: ESLint, Next/TypeScript checks, Prettier and production build pass. **29 farm-state tests pass**.
- Production browser suite: **17 passed**, 3 opt-in tests skipped in that run. Includes the four complete Marketplace workflows plus the 13 preexisting read-only production tests.
- Separate targeted checks: both opt-in legacy research/paper-lifecycle tests pass on dedicated disposable databases; the new calibration empty-state browser test passes with an explicit empty-response fixture. No existing test assertion was removed to achieve compatibility.
- Final rebuilt production frontend against the original database: **14 read-only browser tests passed**, including the calibration empty state. Across the required production, disposable-data and development configurations, **all 21 unique browser tests passed**; they are deliberately not run as one mutating suite against personal data.
- Development browser simulator: **1 passed**, rehearsing 23 event types for each target (46 event selections), including all 10 Marketplace event types. No backend writes.
- Actual Marketplace SSE reached the existing 3D farm for import, price update, purchase and sale. AI-usage counters remained unchanged. Browser workflow detected no external seller/contact requests.
- Native PostgreSQL forward migration `0003 → 0004`: every original table/column preserved; model/schema parity passes; legacy price-history backfill, ten fixtures, duplicate suppression, observed price drop, CSV dry run and actual cost math pass.
- Original database upgraded to `0004`; every preexisting column unchanged. Agent A and Agent B remain **$1,000 each**, with **zero trades**. No verification fixtures were added there.
- Original-stack `/health`, PostgreSQL, Redis, both agent detail/portfolio endpoints, Marketplace APIs and live SSE heartbeat pass.
- Final original-stack readback: zero Marketplace demo rows, zero AI calls, zero AI spend, both balances $1,000.00.
- Mobile Marketplace screenshot inspected; no horizontal overflow. Production farm accessibility, reduced motion, fallback and shared-event behavior remain covered.
- No push or commit performed. No paid AI, external scraping, seller contact, purchase/payment automation or real brokerage execution performed.

## Issues found and fixed

PostgreSQL rejected an overlong explicit foreign-key constraint name; dialect-aware naming fixed it. Browser locators for nested selects/textareas now use their accessible roles. Purchase/sale form reuse retained uncontrolled inputs and open state; distinct keyed instances now require a fresh confirmation. The legacy Marketplace regression check caught hidden prior-phase numeric estimates; the historical estimate block now preserves the full original readout. Calibration excludes fictional fixture outcomes and cannot use predictions made after a backdated purchase.

No unresolved failing check remains. Upstream warnings remain: Starlette/httpx TestClient deprecation, Three.Clock deprecation, Node's typeless-module warning and Playwright color-environment warning. None failed a check. No dependency upgrades were introduced to suppress them.

## Repeat checks

From `backend/` with its virtual environment active:

```sh
python -m pytest -q
ruff check app tests migrations scripts/verify_phase5.py
ruff format --check app tests migrations scripts/verify_phase5.py
alembic check
```

The dedicated forward-migration verifier refuses nonempty databases and databases not named `ai_farm_phase5_verify*`. Privately configure `DATABASE_URL` to a newly created disposable PostgreSQL database with that prefix and `AI_ENABLED=false`, then run from `backend/`:

```sh
PYTHONPATH=. python scripts/verify_phase5.py
```

From `frontend/`:

```sh
npm run lint
npm run typecheck
npm run format:check
npm run test:unit
npm run build
npm run start
```

With the API/frontend running, from another frontend terminal:

```sh
PLAYWRIGHT_CHANNEL=chrome npm run test:e2e
```

For Marketplace mutation tests, first migrate and seed a **fresh disposable database**, point the running API there, enable `LOCAL_WRITES_ENABLED=true`, `ENABLE_DEVELOPMENT_ACTIONS=true`, disable AI/workers, and run:

```sh
MARKETPLACE_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1
```

These tests write real local records and require a fresh fixture namespace. Do not run against personal Marketplace data. Use a separate fresh database for legacy opted-in writes; both the API and test process's `DATABASE_URL` must match:

```sh
PAPER_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1 --grep 'research and Marketplace stream|paper lifecycle updates'
```

Stop production frontend, start `npm run dev`, then in another terminal:

```sh
FARM_DEV_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- tests/farm-development.spec.ts --workers=1
```

From the root, `python3 infra/smoke.py` verifies the original read-only stack and heartbeat. Playwright's bundled Chromium can be used instead by installing it and omitting `PLAYWRIGHT_CHANNEL`. Only Chrome was exercised here.

## Handoff / limitations

Original local API restored with AI/workers disabled and user-initiated local Marketplace writes enabled; frontend available at port 3000. Test data remains only in explicitly named disposable databases; none were dropped. Private `.env` unchanged. Ignored local runtime/test artifacts are not part of the commit.

External approved-source connectors and vision remain unconfigured, not failed integrations. Manual observations, distances, verified costs, sold comps and complete demand cohorts are required for evidence-based results. Tracking does not automatically refresh source pages. USD-only inputs and a 2,000-record ranking window are intentional local-phase limits. See [architecture/startup/demo](phase5-marketplace.md) and [complete changed-file list](phase5-files.md).

Suggested commit: `feat(marketplace): add Phase 5 ingestion, analysis, outcomes and farm integration`
