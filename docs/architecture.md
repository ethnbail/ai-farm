# Phase 1 architecture

## Service boundaries

The Next.js App Router owns pages and presentation. Client data hooks own REST reads and `EventSource` lifecycle; reusable UI components own cards and metrics. Agent details use a real UUID route and separate API data. A later client-only React Three Fiber scene can consume these same hooks and contracts without moving configuration or business logic into scene components. No Three.js dependency or canvas is necessary yet.

FastAPI owns the read-only API, input validation, CORS, generic database-error responses, and SSE transport. SQLAlchemy models and Pydantic schemas are separate. Services compute deterministic balances/returns and trade counts. There are no mutation endpoints, trading decisions, broker integrations, schedulers, or model calls.

PostgreSQL stores agents, trades, opportunities, and system events. Every entity has a UUID key. Money uses fixed-precision Numeric columns; timestamps are timezone-aware in PostgreSQL. Alembic is the schema authority; the app never calls `create_all` at startup. The explicit seed command inserts missing agents by unique name and leaves existing state untouched.

Redis is configured with a development password and health checks. It is reserved for later worker coordination and event transport. Phase 1 deliberately has no queue framework or worker process.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | API, database, Redis status; 503 when degraded |
| GET | `/api/agents` | Real balances, returns, and trade counts |
| GET | `/api/agents/{uuid}` | One agent summary; 404 if absent |
| GET | `/api/agents/{uuid}/trades` | History, newest first; `limit` 1–100, `offset` ≥0 |
| GET | `/api/marketplace` | Actual opportunity count plus unconfigured search state |
| GET | `/api/ai-usage` | Optional budget, disabled status, null usage placeholders |
| GET | `/api/events` | SSE heartbeat stream |

An invalid UUID or pagination argument returns 422. SQLAlchemy failures produce a generic 503 without credentials or SQL in the response. CORS covers only explicitly allowed origins. CORS is not authentication.

Return is `(current_balance - starting_balance) / starting_balance * 100`. There is no mark-to-market engine; balances only represent stored paper-account state. Test-only synthetic trades verify counts. The initial Trade model is a baseline record; options expiry, strikes, contracts, multipliers, fees, and execution semantics are intentionally not modeled yet.

## Live events

Each SSE heartbeat has an `id`, named `event: heartbeat`, and a JSON envelope:

```json
{
  "id": "a-unique-uuid",
  "event_type": "heartbeat",
  "source": "backend",
  "payload": { "status": "alive" },
  "created_at": "an-ISO-8601-UTC-timestamp"
}
```

The first heartbeat is immediate, then repeats every configured interval (1–60 seconds, default 5). A reconnect hint of 3 seconds is sent. The browser reports Live only after receipt, reports Reconnecting on stream error, and warns if no heartbeat arrives for 90 seconds. EventSource is closed when its component unmounts. Disconnects cancel the backend generator. Responses disable cache and reverse-proxy buffering.

The shared event vocabulary already includes `trade_opened`, `trade_closed`, `marketplace_deal_found`, `price_drop_detected`, `agent_status_changed`, and `risk_limit_triggered`. Only `heartbeat` is emitted now. Heartbeats are ephemeral and do not fill SystemEvent with rows. There is no durable subscription, Redis pub/sub, `Last-Event-ID` replay, or cross-process broadcast yet. Future business-event producers should deliberately define delivery/replay semantics before wiring workers to the stream.

## Local infrastructure and deployment path

Compose starts PostgreSQL → one-shot migrations/seed → API, with Redis health gating API startup and API health gating the frontend. It exposes all ports on host loopback. Database volumes persist across normal shutdown. Backend runs as an unprivileged user; frontend runs as the Node image's `node` user. Only frontend source is bind-mounted, avoiding host/container ownership and stale dependency-volume problems.

The Dockerfiles and Compose file are development tooling, not a hardened production deployment. A Proxmox VM can retain the same PostgreSQL/Redis/API/frontend boundaries. Production work includes separate migration execution, production frontend builds, a non-reloading API, TLS, auth, SSE-aware proxy settings, restricted data-service networking, secret rotation, backups, and observability.

## Framework references

- [Next.js App Router setup](https://nextjs.org/docs/app/getting-started/installation)
- [Tailwind CSS with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
- [FastAPI lifecycle management](https://fastapi.tiangolo.com/advanced/events/)
