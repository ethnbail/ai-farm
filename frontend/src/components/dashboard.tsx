"use client";

import Link from "next/link";
import { Badge, ConnectionNotice, Icon, Metric } from "@/components/ui";
import { MarketBanner, RecentActivity } from "@/components/trading";
import { useLiveEvents } from "@/hooks/use-live-events";
import { useResource } from "@/hooks/use-resource";
import { money, percent } from "@/lib/format";
import type { Agent, AIUsage, Health, Marketplace } from "@/lib/types";

function AgentCard({ agent }: { agent: Agent }) {
  const equities = agent.agent_type === "equities";
  return (
    <Link
      href={`/agents/${agent.id}`}
      className={`panel agent-card ${equities ? "equities" : "options"}`}
      aria-label={`View ${agent.name} details`}
    >
      <div className="flex items-start justify-between gap-4">
        <span className="icon-tile">
          <Icon kind={equities ? "field" : "sun"} />
        </span>
        <Badge active={agent.status === "running"}>{agent.status}</Badge>
      </div>
      <h2 className="mt-7 text-2xl font-semibold">{agent.name}</h2>
      <p className="mt-1 text-sm text-muted">
        {equities ? "Equities / ETFs" : "Options"}
      </p>
      <p className="mt-8 text-xs uppercase tracking-widest text-muted">
        Current equity
      </p>
      <p className="mt-2 text-4xl font-medium tracking-tight tabular-nums">
        {money(agent.current_balance)}
      </p>
      <p className="mt-2 text-xs text-muted">
        Valuation: {agent.valuation_state.toUpperCase()} DATA
      </p>
      <dl className="mt-7 grid grid-cols-2 gap-4 border-t border-line pt-5">
        <Metric
          label="Total return"
          value={percent(agent.total_return_percent)}
        />
        <Metric label="Trades" value={agent.total_trades} />
        <Metric label="Open positions" value={agent.open_positions} />
      </dl>
      <div className="mt-7 flex items-center justify-between text-sm font-medium">
        <span>View agent</span>
        <Icon kind="arrow" />
      </div>
    </Link>
  );
}

function MarketplaceCard() {
  const { data, error } = useResource<Marketplace>("/api/marketplace");
  return (
    <section
      className="panel marketplace-card"
      aria-labelledby="marketplace-title"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="icon-tile">
          <Icon kind="basket" />
        </span>
        <Badge>Not configured</Badge>
      </div>
      <h2 id="marketplace-title" className="mt-7 text-2xl font-semibold">
        Marketplace Agent
      </h2>
      <p className="mt-1 text-sm text-muted">
        Local finds, future possibilities.
      </p>
      <ConnectionNotice error={error} />
      <div className="mt-8 grid grid-cols-2 gap-3">
        <label className="text-xs text-muted">
          ZIP code
          <input
            disabled
            placeholder="Not set"
            aria-label="ZIP code"
            className="placeholder-input"
          />
        </label>
        <label className="text-xs text-muted">
          Search radius
          <input
            disabled
            placeholder="Not set"
            aria-label="Search radius"
            className="placeholder-input"
          />
        </label>
      </div>
      <dl className="mt-7 border-t border-line pt-5">
        <Metric
          label="Opportunities found"
          value={data?.opportunities_found ?? "—"}
        />
      </dl>
      <p className="mt-7 text-sm text-muted">
        Search setup will arrive in a later phase.
      </p>
    </section>
  );
}

function SystemCard() {
  const { data, error } = useResource<Health>("/health");
  const live = useLiveEvents();
  const service = (value?: string) =>
    error
      ? "Unreachable"
      : value === "ok"
        ? "Connected"
        : value === "unavailable"
          ? "Unavailable"
          : "Checking";
  return (
    <section className="panel" aria-labelledby="system-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="system-title" className="text-xl font-semibold">
          System
        </h2>
        <span className="eyebrow">Connection health</span>
      </div>
      <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-4">
        <Metric label="Backend" value={service(data?.backend)} />
        <Metric label="Database" value={service(data?.database)} />
        <Metric label="Redis" value={service(data?.redis)} />
        <Metric
          label="Real-time"
          value={
            <span
              data-testid="realtime-status"
              className={live.status === "Live" ? "text-green" : ""}
            >
              {live.status}
            </span>
          }
        />
      </dl>
      <ConnectionNotice error={error} />
      <p className="mt-6 text-xs text-muted" aria-live="polite">
        {live.lastHeartbeat
          ? `Last heartbeat at ${new Date(live.lastHeartbeat).toLocaleTimeString()}`
          : "Waiting for the first backend heartbeat…"}
      </p>
    </section>
  );
}

function AIUsageCard() {
  const { data, error } = useResource<AIUsage>("/api/ai-usage");
  return (
    <section className="panel" aria-labelledby="ai-title">
      <div className="flex items-center justify-between">
        <h2 id="ai-title" className="text-xl font-semibold">
          AI Usage
        </h2>
        <Badge>Disabled</Badge>
      </div>
      <dl className="mt-6 grid grid-cols-3 gap-3">
        <Metric
          label="Monthly budget"
          value={money(data?.monthly_budget_usd)}
        />
        <Metric label="Amount used" value={money(data?.amount_used_usd)} />
        <Metric label="Model calls" value={data?.model_calls ?? "—"} />
      </dl>
      <ConnectionNotice error={error} />
      <p className="mt-6 text-xs text-muted">
        Usage tracking is not configured. No AI calls are enabled.
      </p>
    </section>
  );
}

export function Dashboard() {
  const { data: agents, error } = useResource<Agent[]>("/api/agents");
  return (
    <>
      <div className="mb-9 flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="eyebrow">Your farm, at a glance</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
            Room to grow.
          </h1>
          <p className="mt-4 text-muted">
            A quiet home for your agents. One small step at a time.
          </p>
        </div>
        <Badge active>Paper environment</Badge>
      </div>
      <MarketBanner />
      <ConnectionNotice error={error} />
      <div className="grid gap-5 lg:grid-cols-3">
        {agents?.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
        {!agents && (
          <div className="panel flex min-h-80 flex-col justify-center lg:col-span-2">
            <h2 className="text-xl font-semibold">
              {error ? "Agents unavailable" : "Loading your agents…"}
            </h2>
            <p className="mt-3 text-muted">
              {error
                ? "Check that the backend is running and the database is ready."
                : "Retrieving paper balances from the backend."}
            </p>
          </div>
        )}
        {agents?.length === 0 && (
          <div className="panel lg:col-span-2">
            <h2 className="text-xl font-semibold">
              Your first agents are waiting.
            </h2>
            <p className="mt-3 text-muted">
              Complete the development seed step to add Agent A and Agent B.
            </p>
          </div>
        )}
        <MarketplaceCard />
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[1.3fr_1fr]">
        <SystemCard />
        <AIUsageCard />
      </div>
      <RecentActivity />
      <div className="mt-8 flex items-start gap-3 rounded-2xl border border-line px-5 py-4 text-sm text-muted">
        <Icon className="shrink-0 text-green" />
        <p>
          Independent paper accounts, deterministic rules. Scheduled trading is
          opt-in, and the risk engine may choose not to trade. All balances are
          paper funds.
        </p>
      </div>
    </>
  );
}
