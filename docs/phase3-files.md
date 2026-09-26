# Phase 3 file inventory

Complete working-tree inventory relative to committed Phase 2 baseline `5114fe8`. No staging, commit or push was performed.

26 modified tracked files; 27 new/untracked files. No deleted paths.

```text
 M .env.example
 M README.md
 M backend/app/api/trading.py
 M backend/app/core/config.py
 M backend/app/main.py
 M backend/app/market_data/factory.py
 M backend/app/market_data/mock.py
 M backend/app/market_data/types.py
 M backend/app/models/__init__.py
 M backend/app/models/trading.py
 M backend/app/schemas/events.py
 M backend/app/services/accounting.py
 M backend/app/services/paper_broker.py
 M backend/app/services/risk.py
 M backend/app/workers/cli.py
 M backend/app/workers/scheduler.py
 M backend/pyproject.toml
 M backend/tests/conftest.py
 M backend/tests/test_foundation.py
 M frontend/src/app/layout.tsx
 M frontend/src/components/agent-detail.tsx
 M frontend/src/components/dashboard.tsx
 M frontend/src/hooks/use-live-events.tsx
 M frontend/src/lib/types.ts
 M frontend/tests/dashboard.spec.ts
 M infra/smoke.py
?? backend/app/api/intelligence.py
?? backend/app/market_data/tradier.py
?? backend/app/models/intelligence.py
?? backend/app/schemas/intelligence.py
?? backend/app/services/ai.py
?? backend/app/services/event_context.py
?? backend/app/services/marketplace.py
?? backend/app/services/reliability.py
?? backend/app/services/research.py
?? backend/app/services/shadow.py
?? backend/app/workers/intelligence.py
?? backend/migrations/versions/0003_intelligence.py
?? backend/scripts/verify_phase3.py
?? backend/tests/test_intelligence.py
?? docs/ai-budget.md
?? docs/event-context.md
?? docs/market-regime.md
?? docs/marketplace-intelligence.md
?? docs/model-router.md
?? docs/opportunity-scanner.md
?? docs/phase3-files.md
?? docs/phase3-intelligence.md
?? docs/phase3-verification.md
?? docs/shadow-agent.md
?? frontend/src/app/marketplace/[id]/page.tsx
?? frontend/src/app/research/[id]/page.tsx
?? frontend/src/components/intelligence.tsx
```

`M` = modified, `??` = new/untracked. Private credentials, virtualenvs, dependency installs, native service binaries, test databases, screenshots and build outputs are ignored and intentionally excluded. Existing local verification helpers under `.verification/` are machine-specific; the repeatable native test is committed-source candidate `backend/scripts/verify_phase3.py`.

## Change groups

- Additive migration, research/queue/AI/budget/Shadow/confidence/event/watchlist/Marketplace persistence.
- Read-only Tradier adapter, deterministic regime/features/ranking, original risk/broker orchestration and source-mode protection.
- Optional structured OpenAI routing with transactional budget reservations and deterministic degradation.
- Local watchlist APIs, manual Marketplace connector/scoring/outcomes, reliability and matching-period benchmarks.
- Existing dashboard extended with live research, agent intelligence, usage, ranked contracts and inspectable details.
- Backend/browser/native integration tests, read-only smoke checks, safe config examples and operational docs.

See [verification](phase3-verification.md) for results, limitations and exact startup commands.

Suggested commit: `feat: add Phase 3 paper-only intelligence and research layer`
