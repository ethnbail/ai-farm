# Phase 2 file inventory

Complete working-tree inventory relative to the committed Phase 1 baseline. No files are staged, committed or pushed.

27 modified tracked files, 1 deleted path, 30 new/untracked files. The deleted `use-live-events.ts` is replaced by `use-live-events.tsx` because the shared provider renders JSX; the hook contract remains.

## Files

```text
 M .env.example
?? backend/app/agents/strategies.py
 M backend/app/api/routes.py
?? backend/app/api/trading.py
 M backend/app/core/config.py
 M backend/app/database/seed.py
 M backend/app/main.py
?? backend/app/market_data/__init__.py
?? backend/app/market_data/factory.py
?? backend/app/market_data/mock.py
?? backend/app/market_data/types.py
 M backend/app/models/__init__.py
 M backend/app/models/entities.py
?? backend/app/models/trading.py
 M backend/app/schemas/dashboard.py
 M backend/app/schemas/events.py
?? backend/app/schemas/trading.py
?? backend/app/services/accounting.py
 M backend/app/services/agents.py
?? backend/app/services/event_store.py
 M backend/app/services/events.py
?? backend/app/services/market_hours.py
?? backend/app/services/paper_broker.py
?? backend/app/services/performance.py
?? backend/app/services/risk.py
?? backend/app/services/serialization.py
?? backend/app/workers/cli.py
?? backend/app/workers/engine.py
?? backend/app/workers/scheduler.py
 M backend/migrations/env.py
?? backend/migrations/versions/0002_paper_engine.py
 M backend/pyproject.toml
 M backend/requirements.lock
 M backend/tests/test_foundation.py
?? backend/tests/test_trading.py
 M compose.yaml
 M docs/architecture.md
?? docs/market-data.md
?? docs/paper-broker.md
?? docs/phase2-files.md
?? docs/phase2-verification.md
?? docs/risk-engine.md
?? docs/trading-engine.md
 M docs/verification.md
 M frontend/src/app/layout.tsx
?? frontend/src/app/trades/[id]/page.tsx
 M frontend/src/components/agent-detail.tsx
 M frontend/src/components/dashboard.tsx
?? frontend/src/components/trade-detail.tsx
?? frontend/src/components/trading.tsx
 M frontend/src/components/ui.tsx
 D frontend/src/hooks/use-live-events.ts
?? frontend/src/hooks/use-live-events.tsx
 M frontend/src/hooks/use-resource.ts
 M frontend/src/lib/types.ts
 M frontend/tests/dashboard.spec.ts
 M infra/smoke.py
 M README.md
```

`M` = modified, `D` = removed old path, `??` = new/untracked. Generated credentials, virtualenvs, Node dependencies, build output, screenshots, local service binaries and disposable databases are ignored and deliberately excluded.

## Change groups

- Backend configuration, provider protocols, transparent strategies, broker/risk/accounting, durable events, independent performance and read APIs.
- Migration0002 extends Phase1 records and adds portfolios, positions, orders, fills, option snapshots, risk events, performance snapshots, benchmarks and worker/event state.
- Redis-coordinated opt-in worker and gated local deterministic demo.
- Existing warm frontend extended with positions, history, replay, metrics, activity, freshness labels and one shared EventSource.
- Regression and lifecycle tests, extended smoke checks, Compose paper profile, configuration examples and operational documentation.

See [verification](phase2-verification.md) for results and exact local commands.

Suggested commit message: `feat: add Phase 2 deterministic paper-trading engine`
