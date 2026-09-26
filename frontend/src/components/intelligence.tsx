"use client";

import Link from "next/link";
import { Badge, ConnectionNotice, Metric } from "@/components/ui";
import { amount, timestamp } from "@/components/trading";
import { useResource } from "@/hooks/use-resource";

interface Regime {
  regime: string;
  data_mode: string;
  data_timestamp: string | null;
  reasons: string[];
}
interface Provider {
  provider: string;
  effective_provider: string;
  state: string;
  message: string;
}
interface Usage {
  daily_spend: string;
  monthly_spend: string;
  calls: number;
  denied_calls: number;
  daily_remaining: string;
  monthly_remaining: string;
  enabled: boolean;
  accounting: string;
}
interface AIStatus {
  enabled: boolean;
  mode: string;
  cheap_model: string;
  reasoning_model: string;
  shadow_model: string;
  message: string;
}
export interface Research {
  agent_name: string;
  id: string;
  agent_id: string;
  symbol: string;
  score: string;
  regime: string;
  data_mode: string;
  eligible: boolean;
  reasons: string[];
  rejection_reasons: string[];
  components: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  proposal: Record<string, unknown>;
  queue: {
    status: string;
    rank: number;
    ai_status: string;
    shadow_status: string;
    risk_status: string;
    rejection_reason: string | null;
    trade_id: string | null;
  } | null;
  analyses?: {
    model: string;
    status: string;
    analysis: Record<string, unknown>;
  }[];
  shadow_reviews?: {
    model: string;
    status: string;
    review: Record<string, unknown>;
  }[];
}
interface Listing {
  id: string;
  title: string;
  source: string;
  asking_price: string;
  direct_url: string;
  details: Record<string, unknown>;
  analyses: { analysis: Record<string, unknown> }[];
  outcome?: Record<string, unknown> | null;
}
interface AgentIntelligence {
  latest_research: Research | null;
  watchlist: string[];
  strategy_version: string;
  model_version: string;
  baseline: string;
  reliability: {
    decisions: number;
    completed: number;
    win_rate: string | null;
    brier_score: string | null;
    minimum_samples: number;
  }[];
  risk_rejections: { rule: string; details: Record<string, unknown> }[];
}

export function Facts({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className="mt-4 grid min-w-0 gap-4 sm:grid-cols-2">
      {Object.entries(value).map(([key, item]) => (
        <div key={key} className="min-w-0">
          <dt className="text-xs uppercase tracking-wide text-muted">
            {key.replaceAll("_", " ")}
          </dt>
          <dd className="mt-1 break-words text-sm">
            {item == null ? (
              "N/A"
            ) : typeof item === "object" ? (
              <pre className="max-w-full whitespace-pre-wrap break-all font-sans text-xs">
                {JSON.stringify(item, null, 2)}
              </pre>
            ) : (
              String(item)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function AIUsagePanel() {
  const usage = useResource<Usage>("/api/ai/usage");
  const status = useResource<AIStatus>("/api/ai/status");
  return (
    <section className="panel" aria-label="AI Usage">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">AI Usage</h2>
        <Badge>{status.data?.enabled ? status.data.mode : "Disabled"}</Badge>
      </div>
      <ConnectionNotice error={usage.error ?? status.error} />
      <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
        <Metric label="Daily spend" value={amount(usage.data?.daily_spend)} />
        <Metric
          label="Monthly spend"
          value={amount(usage.data?.monthly_spend)}
        />
        <Metric label="Calls today" value={usage.data?.calls ?? "N/A"} />
        <Metric
          label="Daily remaining"
          value={amount(usage.data?.daily_remaining)}
        />
        <Metric
          label="Monthly remaining"
          value={amount(usage.data?.monthly_remaining)}
        />
        <Metric
          label="Denied calls"
          value={usage.data?.denied_calls ?? "N/A"}
        />
      </dl>
      <p className="mt-5 text-xs text-muted">
        {status.data?.mode ?? "Checking"} ·{" "}
        {usage.data?.accounting ?? "Usage unavailable"}
      </p>
      <p className="mt-2 text-xs text-muted">
        Models: {status.data?.cheap_model ?? "N/A"} /{" "}
        {status.data?.reasoning_model ?? "N/A"} · Shadow{" "}
        {status.data?.shadow_model ?? "N/A"}
      </p>
    </section>
  );
}

export function IntelligencePanel({ agentId }: { agentId?: string }) {
  const regime = useResource<Regime>("/api/market/regime");
  const provider = useResource<Provider>("/api/market/provider-status");
  const research = useResource<Research[]>(
    `/api/research?latest_scan=true&limit=6${agentId ? `&agent_id=${agentId}` : ""}`,
  );
  return (
    <section
      className="panel mt-5"
      aria-label={agentId ? "Agent Intelligence" : "Market intelligence"}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">
          {agentId ? "Intelligence" : "Market regime"}
        </h2>
        <Badge>{regime.data?.regime.replaceAll("_", " ") ?? "UNKNOWN"}</Badge>
      </div>
      <ConnectionNotice
        error={regime.error ?? provider.error ?? research.error}
      />
      <p className="mt-3 text-xs text-muted">
        {regime.data?.data_mode.toUpperCase() ?? "UNAVAILABLE"} DATA ·{" "}
        {timestamp(regime.data?.data_timestamp)}
      </p>
      <p className="mt-2 text-sm">
        Provider: {provider.data?.effective_provider ?? "Unavailable"} ·{" "}
        {provider.data?.message ?? "Checking provider"}
      </p>
      {agentId && <AgentContext id={agentId} />}
      <h3 className="mt-6 font-semibold">
        Opportunity queue · Recent research
      </h3>
      {research.data?.length === 0 && (
        <p className="mt-3 text-sm text-muted">
          No research yet. Run an explicit research scan; AI is optional.
        </p>
      )}
      {!research.data && !research.error && (
        <p className="mt-3 text-muted">Loading research…</p>
      )}
      <ul className="mt-4 divide-y divide-line">
        {research.data?.map((r) => (
          <li key={r.id} className="py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Link
                className="font-semibold text-green hover:underline"
                href={`/research/${r.id}`}
              >
                {r.symbol} research
              </Link>
              <Badge>{r.queue?.status ?? "DISCOVERED"}</Badge>
            </div>
            <p className="mt-2 text-sm">
              {r.agent_name} · Score {Number(r.score).toFixed(1)} ·{" "}
              {r.data_mode.toUpperCase()} · Rank {r.queue?.rank ?? "N/A"}
            </p>
            <p className="mt-1 text-xs text-muted">
              AI: {r.queue?.ai_status ?? "pending"} · Shadow:{" "}
              {r.queue?.shadow_status ?? "pending"} · Risk:{" "}
              {r.queue?.risk_status ?? "not reviewed"}
            </p>
            <p className="mt-2 text-xs text-muted">
              {r.queue?.rejection_reason ||
                r.rejection_reasons.join("; ") ||
                r.reasons.join("; ")}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AgentContext({ id }: { id: string }) {
  const { data, error } = useResource<AgentIntelligence>(
    `/api/agents/${id}/intelligence`,
  );
  return (
    <div className="mt-4 text-sm">
      <ConnectionNotice error={error} />
      <p>Watchlist / universe: {data?.watchlist.join(", ") ?? "Loading"}</p>
      <p className="mt-2 text-xs text-muted">
        Strategy: {data?.strategy_version ?? "N/A"}
        {" · Model: "}
        {data?.model_version ?? "N/A"}
      </p>
      <p className="mt-2 text-xs text-muted">{data?.baseline}</p>
      {data?.latest_research && (
        <details className="mt-4">
          <summary>
            Latest analysis and Shadow review · {data.latest_research.symbol}
          </summary>
          {data.latest_research.analyses?.map((a, i) => (
            <Facts
              key={`a${i}`}
              value={{
                model: a.model,
                recommendation: a.analysis.recommendation,
                thesis: a.analysis.thesis,
              }}
            />
          ))}
          {data.latest_research.shadow_reviews?.map((s, i) => (
            <Facts
              key={`s${i}`}
              value={{
                shadow_model: s.model,
                objections: s.review.objections,
                action: s.review.recommended_action,
              }}
            />
          ))}
          <ContractRanking snapshot={data.latest_research.snapshot} />
        </details>
      )}
      <p className="mt-2 text-xs text-muted">
        Reliability:{" "}
        {data?.reliability.length
          ? data.reliability
              .map(
                (r) =>
                  `${r.completed} outcomes / ${r.decisions} decisions · Win rate ${r.win_rate == null ? "N/A" : `${(Number(r.win_rate) * 100).toFixed(1)}%`} · Calibration ${r.brier_score ?? "N/A"} (minimum ${r.minimum_samples} outcomes)`,
              )
              .join("; ")
          : "N/A — no completed research outcomes"}
      </p>
      {!!data?.risk_rejections.length && (
        <details className="mt-3">
          <summary>Recent risk rejections</summary>
          <ul className="mt-2 space-y-2">
            {data.risk_rejections.map((r, i) => (
              <li key={i}>
                {r.rule}: {String(r.details.reason ?? "Rejected")}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ContractRanking({ snapshot }: { snapshot: Record<string, unknown> }) {
  const rows = snapshot.ranked_contracts as
    | {
        quote: Record<string, unknown>;
        score: string;
        rejection_reasons: string[];
      }[]
    | undefined;
  if (!rows?.length) return null;
  return (
    <div className="mt-5 overflow-x-auto">
      <h3 className="font-semibold">Ranked option contracts</h3>
      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr>
            {[
              "Contract",
              "DTE",
              "Delta",
              "IV",
              "Spread %",
              "Volume",
              "OI",
              "Score / Rejection",
            ].map((s) => (
              <th key={s} className="p-2">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.quote.symbol)} className="border-t border-line">
              {[
                r.quote.symbol,
                r.quote.dte,
                r.quote.delta,
                r.quote.iv,
                r.quote.spread_percent,
                r.quote.volume,
                r.quote.open_interest,
                `${r.score} · ${r.rejection_reasons.join(", ") || "Eligible"}`,
              ].map((v, i) => (
                <td key={i} className="p-2">
                  {v == null ? "N/A" : String(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MarketplaceIntelligence() {
  const { data, error } = useResource<Listing[]>(
    "/api/marketplace/opportunities?limit=3",
  );
  return (
    <section className="panel mt-5" aria-label="Marketplace intelligence">
      <h2 className="text-xl font-semibold">Marketplace intelligence</h2>
      <p className="mt-2 text-xs text-muted">
        Manual imports and test fixtures only. No scraping, messaging or
        purchasing.
      </p>
      <ConnectionNotice error={error} />
      {data?.length === 0 && (
        <p className="mt-4 text-sm text-muted">
          No imported opportunities yet.
        </p>
      )}
      {data?.map((l) => (
        <article key={l.id} className="mt-4 rounded-xl border border-line p-4">
          <Link
            className="font-semibold text-green hover:underline"
            href={`/marketplace/${l.id}`}
          >
            {l.title}
          </Link>
          <p className="mt-2 text-sm">
            {l.source.toUpperCase()} · Asking {amount(l.asking_price)} ·
            Estimated net{" "}
            {amount(
              l.analyses[0]?.analysis.expected_net_profit as string | null,
            )}
          </p>
          <p className="mt-2 text-xs text-muted">
            Sale time: N/A ·{" "}
            {String(
              (
                l.analyses[0]?.analysis.risk_flags as string[] | undefined
              )?.join("; ") ?? "Unverified",
            )}
          </p>
        </article>
      ))}
    </section>
  );
}

export function ResearchDetail({ id }: { id: string }) {
  const { data: r, error } = useResource<Research>(`/api/research/${id}`);
  return (
    <>
      <Link className="text-green hover:underline" href="/">
        ← Back to farm
      </Link>
      <h1 className="my-7 break-words text-3xl font-semibold">
        {r
          ? `${r.symbol} research`
          : error
            ? "Research unavailable"
            : "Loading research…"}
      </h1>
      <ConnectionNotice error={error} />
      {r && (
        <>
          <section className="panel">
            <h2 className="text-xl font-semibold">Deterministic decision</h2>
            <Facts
              value={{
                score: r.score,
                regime: r.regime,
                data_mode: r.data_mode,
                eligible: r.eligible,
                reasons: r.reasons,
                rejection_reasons: r.rejection_reasons,
                queue: r.queue,
                score_components: r.components,
              }}
            />
            {r.queue?.trade_id && (
              <Link
                className="mt-4 block text-green underline"
                href={`/trades/${r.queue.trade_id}`}
              >
                View executed paper trade
              </Link>
            )}
          </section>
          <section className="panel mt-5">
            <h2 className="text-xl font-semibold">Strategy proposal</h2>
            <Facts value={r.proposal} />
          </section>
          <section className="panel mt-5">
            <h2 className="text-xl font-semibold">Analysis</h2>
            {r.analyses?.map((a, i) => (
              <div key={i}>
                <p className="mt-3 text-xs text-muted">
                  {a.model} · {a.status}
                </p>
                <Facts value={a.analysis} />
              </div>
            ))}
            {!r.analyses?.length && (
              <p className="mt-4 text-muted">
                Not analyzed: deterministic filters did not shortlist this
                candidate.
              </p>
            )}
          </section>
          <section className="panel mt-5">
            <h2 className="text-xl font-semibold">Shadow objections</h2>
            {r.shadow_reviews?.map((s, i) => (
              <div key={i}>
                <p className="mt-3 text-xs text-muted">
                  {s.model} · {s.status}
                </p>
                <Facts value={s.review} />
              </div>
            ))}
            {!r.shadow_reviews?.length && (
              <p className="mt-4 text-muted">No Shadow review required.</p>
            )}
          </section>
          <section className="panel mt-5">
            <h2 className="text-xl font-semibold">
              Normalized market snapshot
            </h2>
            <ContractRanking snapshot={r.snapshot} />
            <Facts value={r.snapshot} />
          </section>
        </>
      )}
    </>
  );
}

export function MarketplaceDetail({ id }: { id: string }) {
  const { data, error } = useResource<Listing>(
    `/api/marketplace/opportunities/${id}`,
  );
  return (
    <>
      <Link className="text-green hover:underline" href="/">
        ← Back to farm
      </Link>
      <h1 className="my-7 text-3xl font-semibold">
        {data?.title ?? "Marketplace estimate"}
      </h1>
      <ConnectionNotice error={error} />
      {data && (
        <section className="panel">
          <Badge>{data.source} · Estimates only</Badge>
          <Facts value={data.details} />
          {data.analyses.map((a, i) => (
            <Facts key={i} value={a.analysis} />
          ))}
          <a
            href={data.direct_url}
            target="_blank"
            rel="noreferrer"
            className="mt-5 block text-green underline"
          >
            Open original listing
          </a>
          <h2 className="mt-6 text-xl font-semibold">Recorded outcome</h2>
          {data.outcome ? (
            <Facts value={data.outcome} />
          ) : (
            <p className="mt-3 text-muted">
              No purchase or sale outcome recorded.
            </p>
          )}
        </section>
      )}
    </>
  );
}
