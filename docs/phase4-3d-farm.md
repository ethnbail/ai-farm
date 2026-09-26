# Phase 4: the live AI Farm

The root page is a client-loaded React Three Fiber scene with original procedural geometry, warm fixed daylight, soft filtered shadows, paths, a pond, trees, a vegetable patch and fences. This is a read-only visualization of the existing backend, not a second trading engine. No backend files, schemas, trading rules, balances, credentials or execution paths changed.

## Architecture

`layout → LiveEventsProvider → FarmExperience → FarmProvider → FarmWorld → lazy FarmScene`

The layout owns one EventSource across route transitions. A validated, deduplicated dispatcher sends business events to the farm state controller and the existing resource-refresh event. FarmProvider batches existing GET endpoints into a typed React context: agents, portfolios, positions, performance, intelligence, research/Shadow records, listings, watchlists, health, regime, AI usage and activity. A 15-second reconciliation poll supplements debounced SSE refreshes. Requests are aborted on unmount and never overlap. Failed feeds retain last-known data with an explicit warning; missing financial values are not invented.

The pure state machine lives in `frontend/src/lib/farm-state.ts`; the renderer only consumes its states and short-lived motion records. Frame callbacks change transforms rather than React state. The development simulator uses the same transition function but does not dispatch a resource refresh or make API writes. There is no animation-to-backend execution path.

## Buildings and characters

| Area | Building | Original mascot | Opens |
| --- | --- | --- | --- |
| Agent A | Rust-red equity barn | Small horned ox | Equity, return, positions, state, opportunity, regime and full agent route |
| Agent B | Teal options observatory | Broad-eyed owl | Equity, options positions, candidate/held contract, DTE, delta, candidate spread |
| Marketplace | Ochre market stall | Masked raccoon | Recent listings ranked by estimated net, risks, distance, sale-time and detail links |
| Research | Sage reading room | Scholarly mole | Current research, queue state, watchlists and research routes |
| Shadow | Slate shed and perch | Muted crow | Review status and latest recorded objections |
| Treasury | Central farmhouse and silo | None | Display-only combined paper totals, separate agent balances, AI usage and system health |
| Analytics | Signal windmill | None | Returns, drawdown, benchmark availability and sample limitations |

The camera smoothly focuses the selected area, supports bounded orbit/zoom and bounded desktop panning, and has a reset button. Mobile disables pan and automatically reduces rendering complexity. Desktop panels are nonmodal; narrow screens use an accessible bottom sheet. Existing `/agents/{id}`, `/trades/{id}`, `/research/{id}` and `/marketplace/{id}` routes remain intact.

## Settings and fallback

- `NEXT_PUBLIC_ENABLE_3D_FARM=false`: force 2D. Default true.
- `NEXT_PUBLIC_REDUCED_SCENE=true`: initially use simplified rendering. Default false; narrow viewports also simplify.
- **Switch to 2D / Explore in 3D** persists `ai-farm:3d` locally.
- **Reduced motion** persists `ai-farm:reduced-motion`; OS `prefers-reduced-motion` always takes priority and uses 2D.
- Unavailable WebGL2, context loss, render exceptions, or sustained poor performance use the original complete Dashboard, not a screenshot or placeholder.

Public variables are safe configuration only and are embedded during production build. Never put backend secrets in them. See [Next.js environment-variable documentation](https://nextjs.org/docs/app/guides/environment-variables) and [lazy-loading documentation](https://nextjs.org/docs/app/guides/lazy-loading).

## Run the visual simulator

With PostgreSQL, Redis and the existing API running, from `frontend/`:

```sh
npm ci
NEXT_TELEMETRY_DISABLED=1 npm run dev
```

Open http://localhost:3000, enable 3D (and disable user/OS reduced motion if you want animation), scroll below the farm, and expand **DEVELOPMENT ONLY · Farm Event Simulator**. Choose Agent A or B and press event buttons. A persistent visual-rehearsal banner distinguishes simulations from real records. **Reset rehearsal** clears temporary overrides. Financial figures always remain backend values. No worker, demo trade, AI key, database fixture or paid model call is needed.

The simulator import and callback are gated by `NODE_ENV === "development"`; `npm run build && npm run start` does not expose it.

## Limitations retained deliberately

Markets remain mock by default; empty research/listing areas stay empty. Marketplace sale-time/probability estimates remain N/A where the backend has no evidence. The scene parcel represents research inventory, never an actual purchase. Phase 3 has no listing dismissal endpoint/event or live price-monitor emitter: no dismissal is fabricated; the supported price-drop visual can be rehearsed, but live price-drop automation is not implemented. Listings disappearing from the backend remove the aggregate parcel on refresh; individual parcel logistics are not modeled.

Characters use transform animation, not skeletal rigs. Fixed golden-hour lighting is intentional. No sound, post-processing, generated raster art, copied game assets, cloud deployment, brokerage connection or new paid service was added. Detailed per-trade execution/replay remains in existing routes. Authentication and production hardening remain outside this local development phase.

Related: [animations](farm-animation-system.md), [event mapping](farm-event-mapping.md), [performance](farm-performance.md), [accessibility](farm-accessibility.md), [assets](farm-assets.md), [verification](phase4-verification.md), [files](phase4-files.md).
