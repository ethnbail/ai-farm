# Phase 5 changed-file inventory

Git status at final handoff: **21 modified tracked files**, **33 untracked new files**. Nothing staged, committed or pushed. Paths below are repository-relative. Private configuration, test databases, installed runtimes, build output and browser artifacts are ignored and excluded.

```text
 M .env.example
 M backend/app/api/intelligence.py
?? backend/app/api/marketplace.py
 M backend/app/core/config.py
 M backend/app/main.py
?? backend/app/marketplace/__init__.py
?? backend/app/marketplace/analysis.py
?? backend/app/marketplace/cli.py
?? backend/app/marketplace/connectors.py
?? backend/app/marketplace/fixtures.py
?? backend/app/marketplace/pipeline.py
 M backend/app/models/__init__.py
 M backend/app/models/intelligence.py
?? backend/app/models/marketplace.py
 M backend/app/schemas/events.py
?? backend/app/schemas/marketplace.py
?? backend/migrations/versions/0004_marketplace.py
?? backend/scripts/verify_phase5.py
 M backend/tests/test_foundation.py
?? backend/tests/test_marketplace.py
?? docs/examples/marketplace-listings.csv
?? docs/examples/marketplace-listings.json
?? docs/marketplace-calibration.md
?? docs/marketplace-connectors.md
?? docs/marketplace-inventory.md
?? docs/marketplace-outcomes.md
?? docs/marketplace-risk.md
?? docs/marketplace-scoring.md
?? docs/marketplace-sell-through.md
?? docs/marketplace-valuation.md
?? docs/phase5-files.md
?? docs/phase5-marketplace.md
?? docs/phase5-verification.md
 M frontend/src/app/globals.css
 M frontend/src/app/layout.tsx
 M frontend/src/app/marketplace/[id]/page.tsx
?? frontend/src/app/marketplace/calibration/page.tsx
?? frontend/src/app/marketplace/import/page.tsx
?? frontend/src/app/marketplace/inventory/page.tsx
?? frontend/src/app/marketplace/new/page.tsx
?? frontend/src/app/marketplace/page.tsx
?? frontend/src/app/marketplace/settings/page.tsx
 M frontend/src/components/farm/farm-experience.tsx
 M frontend/src/components/farm/farm-scene.tsx
 M frontend/src/components/farm/farm-simulator.tsx
 M frontend/src/components/farm/farm-store.tsx
 M frontend/src/components/intelligence.tsx
?? frontend/src/components/marketplace.tsx
 M frontend/src/lib/farm-state.ts
 M frontend/src/lib/types.ts
 M frontend/tests/farm-development.spec.ts
 M frontend/tests/farm-state.test.mjs
?? frontend/tests/marketplace.spec.ts
 M README.md
```

Backend changes are additive Marketplace models, migration, normalization, deterministic analysis, local APIs, fixtures and tests. Frontend changes add the workbench and extend the existing shared farm event/store architecture. No brokerage, paper accounting or risk-engine implementation was replaced. Documentation and import templates are included.

