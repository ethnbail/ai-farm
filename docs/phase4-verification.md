# Phase 4 verification

Verified locally on macOS with Node 24, Python 3.12, installed Chrome, PostgreSQL 17 and Redis 7.4. The API used mock market data, disabled AI and disabled workers. Phase 4 changed no backend source or migration. Original Agent A and Agent B remain idle at $1,000.00 each; the original database has zero trades and zero AI usage records. No paid provider call, paper execution, real-money integration, commit or push was performed.

## Checks

| Check | Result |
| --- | --- |
| Backend regression suite | 123 passed; isolated SQLite test data |
| Pure farm transition suite | 20 passed |
| Frontend lint, types, formatting | Passed |
| Next.js production build | Passed; all prior routes retained |
| Read-only production Chrome suite | 13 passed: five previous dashboard checks plus eight farm checks |
| Legacy mutation tests | Two intentionally skipped: require `PAPER_E2E=1` and a disposable database |
| Development simulator suite | One passed, replaying all 14 supported buttons for Agent A and Agent B |
| Simulator in production | Absent from UI; development test intentionally skipped in production run |
| Rendering | Real WebGL canvas ready; all seven labels/building buttons present; click opens correct panel |
| SSE | Actual backend heartbeat; injected named events exercise normalized dispatcher, A/B isolation, Shadow, Marketplace, stale/restore, duplicate-ID suppression and one stream across navigation |
| Safety | Replay makes no backend writes; original agents unchanged before/after browser runs; DB count and AI usage independently checked |
| Accessibility / mobile | Keyboard focus and Escape return, 390px no-overflow layout, bottom-sheet details, persisted 2D choice, OS reduced motion |
| Failure behavior | Unavailable WebGL and actual context loss both recover to the live 2D dashboard |
| API / data services | `/health`: backend, database and Redis all `ok`; `/api/agents` and AI usage read successfully |

The event-injection tests deliberately do not create trades just to exercise animations. Real backend business-event publishing and mutation scenarios were verified in Phase 3; those historical results are in [phase3-verification.md](phase3-verification.md). This phase verifies the new visual consumer with real GET data and safe local event injection.

## Reproducible commands

With local API/data services running and an idle seeded database, from `frontend/`:

```sh
npm ci
npm run lint
npm run typecheck
npm run format:check
npm run test:unit
NEXT_TELEMETRY_DISABLED=1 npm run build
NEXT_TELEMETRY_DISABLED=1 npm run start
# Separate terminal, same frontend directory. Do NOT set PAPER_E2E on valuable data.
PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- --workers=1
```

Stop the production frontend before development verification:

```sh
NEXT_TELEMETRY_DISABLED=1 npm run dev
# Separate terminal, from frontend/:
FARM_DEV_E2E=1 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e -- tests/farm-development.spec.ts --workers=1
```

Without installed Chrome, install Playwright Chromium and omit `PLAYWRIGHT_CHANNEL=chrome`. Running production-only UI tests against a dev server is intentionally not equivalent: the simulator should exist in development. Keep `PAPER_E2E` unset for all normal visual testing.

Backend regression command, from `backend/`:

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider
```

## Exact native startup on this existing Mac

These commands reuse ignored local dependencies. Fresh clones should follow the portable Docker/native setup in README. Start only one frontend/backend pair; verification processes are stopped at handoff.

```sh
# Terminal 1: Ctrl-C stops the native PostgreSQL and Redis helpers.
cd /Users/ethanbailey/Documents/ai-farm
backend/.venv/bin/python .verification/services.py
```

```sh
# Terminal 2: existing original DB, read-only visualization configuration.
cd /Users/ethanbailey/Documents/ai-farm/backend
AI_ENABLED=false MARKET_DATA_PROVIDER=mock PAPER_WORKER_ENABLED=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
# Terminal 3: development farm and visual simulator.
cd /Users/ethanbailey/Documents/ai-farm/frontend
export PATH="/Users/ethanbailey/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH"
NEXT_TELEMETRY_DISABLED=1 node ../.tools/npm/bin/npm-cli.js run dev
```

Open http://localhost:3000. Expand **DEVELOPMENT ONLY · Farm Event Simulator**, choose either agent, then select events. Reset rehearsal clears only visual overrides. No CLI trade/demo command is necessary. For production UI, stop dev, run `NEXT_TELEMETRY_DISABLED=1 node ../.tools/npm/bin/npm-cli.js run build`, then the same command with `run start`.

## Artifacts and limitations

Browser screenshots are ignored generated artifacts:

- `frontend/test-results/farm-3D-farm-renders-with--026f1-ings-and-unchanged-balances-chromium/farm-desktop.png`
- `frontend/test-results/farm-mobile-farm-fits-bott-a9fe6-production-has-no-simulator-chromium/farm-mobile.png`

Reviewed desktop/mobile renders, including camera fit, seven labels and persistent paper labeling. Tests overwrite their own result directories. The [performance notes](farm-performance.md) give actual local samples and clarify that a mobile viewport is not a physical-phone benchmark. Safari, physical phones/tablets, assistive technology, sustained memory profiling and Docker image boot were not revalidated in Phase 4. Manual hardware/accessibility smoke testing remains prudent before wider use.

Warnings: upstream Three.Clock deprecation through Fiber; Starlette/httpx TestClient deprecation; Playwright NO_COLOR/FORCE_COLOR warning; Node's TypeScript module-detection warning in unit tests. npm initially warned about a blocked existing unrs-resolver install script; the verified lint/types/build did not require enabling it. The npm audit after adding rendering dependencies reported zero vulnerabilities. These do not represent failing checks.

Resolved during verification: first floating label lost by a shared DOM mount (dedicated label portal), mobile camera crop (viewport-fit zoom), removed Three shadow-map default (explicit supported PCF map), and misleading elapsed-time load measurement (mount-to-first-frame timing). An initial development Chrome navigation reported `ERR_NETWORK_IO_SUSPENDED`; retries passed. One build attempted Next telemetry settings outside the sandbox; rerunning with telemetry disabled passed. An approval-service usage limit temporarily blocked a repeat browser check; it passed after continuation. None required weakening backend safety.

No current failing automated check is known. Missing live Marketplace price-drop/dismissal data is explicitly documented rather than invented. Default mock feeds, empty original research/listings and unavailable statistical benchmarks remain intentional backend limitations, not animated substitutes.
