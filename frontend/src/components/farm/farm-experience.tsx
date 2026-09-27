"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Component, useCallback, useEffect, useRef, useState } from "react";
import { Dashboard } from "@/components/dashboard";
import { amount, rate } from "@/components/trading";
import { areas, buildings, type Area } from "@/lib/farm-state";
import type {
  Agent,
  LiveEvent,
  Performance,
  Portfolio,
  Position,
} from "@/lib/types";
import type { Research } from "@/components/intelligence";
import {
  FarmProvider,
  useFarm,
  type Listing,
  type Regime,
  type Usage,
} from "./farm-store";
import type { SceneMetrics } from "./farm-scene";

const Scene = dynamic(() => import("./farm-scene"), {
  ssr: false,
  loading: () => (
    <div className="farm-loading">
      AI FARM<span>Waking up the farm…</span>
    </div>
  ),
});
const Simulator =
  process.env.NODE_ENV === "development"
    ? dynamic(() => import("./farm-simulator"), { ssr: false })
    : null;

class SceneBoundary extends Component<
  { children: React.ReactNode; onFailure: (reason: string) => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure(
      "3D could not start. The complete 2D dashboard is still live.",
    );
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function FarmExperience() {
  const [ready, setReady] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [reduced, setReduced] = useState(false);
  const [systemReduced, setSystemReduced] = useState(false);
  const [failure, setFailure] = useState("");
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const init = setTimeout(() => {
      try {
        setEnabled(localStorage.getItem("ai-farm:3d") !== "false");
        setReduced(localStorage.getItem("ai-farm:reduced-motion") === "true");
      } catch {
        /* Storage is optional. */
      }
      setSystemReduced(media.matches);
      setReady(true);
    }, 0);
    const change = () => setSystemReduced(media.matches);
    media.addEventListener("change", change);
    return () => {
      clearTimeout(init);
      media.removeEventListener("change", change);
    };
  }, []);
  const allowed = process.env.NEXT_PUBLIC_ENABLE_3D_FARM !== "false";
  const show =
    ready && enabled && allowed && !reduced && !systemReduced && !failure;
  const fail = useCallback((reason: string) => {
    setFailure(reason);
    document.body.style.cursor = "auto";
  }, []);
  function preference(key: string, value: boolean) {
    try {
      localStorage.setItem(key, String(value));
    } catch {
      /* Private browsing still works. */
    }
  }
  return (
    <>
      <div className="farm-preferences">
        <p>
          <strong>PAPER TRADING</strong>
          <span>Simulated accounts only · No real money</span>
        </p>
        <div>
          <button
            aria-pressed={enabled && allowed}
            disabled={!allowed}
            onClick={() => {
              setEnabled(!enabled);
              preference("ai-farm:3d", !enabled);
              setFailure("");
            }}
          >
            {enabled && allowed ? "Switch to 2D" : "Explore in 3D"}
          </button>
          <label>
            <input
              type="checkbox"
              checked={reduced || systemReduced}
              disabled={systemReduced}
              onChange={(e) => {
                setReduced(e.target.checked);
                preference("ai-farm:reduced-motion", e.target.checked);
              }}
            />{" "}
            Reduced motion
          </label>
        </div>
      </div>
      {!ready ? (
        <div className="farm-loading">
          AI FARM<span>Waking up the farm…</span>
        </div>
      ) : show ? (
        <FarmProvider>
          <FarmWorld onFailure={fail} />
        </FarmProvider>
      ) : (
        <>
          <p className="farm-fallback" role="status">
            {failure ||
              (reduced || systemReduced
                ? "Reduced motion is on. All features are available in the calm 2D dashboard."
                : "2D dashboard · Live data, full functionality.")}
            {failure && (
              <button onClick={() => setFailure("")}>Retry 3D</button>
            )}
          </p>
          <Dashboard />
        </>
      )}
    </>
  );
}

function FarmWorld({ onFailure }: { onFailure: (reason: string) => void }) {
  const farm = useFarm();
  const [selected, setSelected] = useState<Area | null>(null);
  const [reset, setReset] = useState(0);
  const [simplified, setSimplified] = useState(
    process.env.NEXT_PUBLIC_REDUCED_SCENE === "true",
  );
  const [active, setActive] = useState(true);
  const [rendererReady, setRendererReady] = useState(false);
  const [metrics, setMetrics] = useState<SceneMetrics | null>(null);
  const region = useRef<HTMLDivElement>(null);
  const labelPortal = useRef<HTMLDivElement>(null!);
  const panel = useRef<HTMLElement>(null);
  const slow = useRef(0);
  const started = useRef(0);
  const sceneLoadMs = useRef(0);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    started.current = performance.now();
    const probe = document.createElement("canvas");
    const gl = probe.getContext("webgl2");
    if (!gl) {
      onFailure("WebGL unavailable. Your live 2D dashboard is ready.");
      return;
    }
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    const mobile = window.matchMedia("(max-width: 700px)");
    const resize = () => {
      if (mobile.matches) setSimplified(true);
    };
    const tick = setTimeout(resize, 0);
    let visible = true;
    const visibility = () => setActive(visible && !document.hidden);
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        visibility();
      },
      { rootMargin: "100px" },
    );
    if (region.current) observer.observe(region.current);
    document.addEventListener("visibilitychange", visibility);
    mobile.addEventListener("change", resize);
    return () => {
      clearTimeout(tick);
      observer.disconnect();
      document.removeEventListener("visibilitychange", visibility);
      mobile.removeEventListener("change", resize);
      document.body.style.cursor = "auto";
    };
  }, [onFailure]);
  useEffect(() => {
    if (selected) panel.current?.focus();
  }, [selected]);
  const onMetrics = useCallback(
    (sample: SceneMetrics) => {
      setMetrics({ ...sample, loadMs: sceneLoadMs.current });
      if (performance.now() - started.current < 10_000) return;
      slow.current = sample.fps < 20 ? slow.current + 1 : 0;
      if (slow.current >= 3) {
        slow.current = 0;
        if (!simplified) setSimplified(true);
        else
          onFailure(
            "Rendering is slow on this device. Switched to the full 2D dashboard.",
          );
      }
    },
    [simplified, onFailure],
  );
  const onReady = useCallback(() => {
    sceneLoadMs.current = Math.round(performance.now() - started.current);
    setRendererReady(true);
  }, []);
  const select = useCallback((area: Area) => {
    opener.current = document.activeElement as HTMLElement;
    setSelected(area);
  }, []);
  const close = () => {
    setSelected(null);
    opener.current?.focus();
  };
  const regime = farm.cache["/api/market/regime"]?.error
    ? undefined
    : farm.get<Regime>("/api/market/regime");
  const usage = farm.get<Usage>("/api/ai/usage");
  const listings = farm.get<Listing[]>(
    "/api/marketplace/opportunities?limit=100",
  );
  const research = farm.get<Research[]>(
    "/api/research?latest_scan=true&limit=6",
  );
  const events = farm.get<LiveEvent[]>("/api/activity?limit=8");
  return (
    <div className="farm-experience">
      <div className="farm-heading">
        <div>
          <p className="eyebrow">A little world. Real system state.</p>
          <h1>Room to grow.</h1>
        </div>
        <p>
          Quietly watching.
          <br />
          Thoughtfully working.
        </p>
      </div>
      <div
        className="farm-stage"
        ref={region}
        data-testid="farm-stage"
        data-renderer={rendererReady ? "ready" : "loading"}
      >
        <div className="farm-hud">
          <span data-testid="realtime-status">{farm.live.status}</span>
          <span>
            {farm.market?.data_state.toUpperCase() ?? "UNAVAILABLE"} DATA
          </span>
          <span>{regime?.regime.replaceAll("_", " ") ?? "UNKNOWN"}</span>
          <span>
            {farm.cache["/api/ai/usage"]?.error || !usage
              ? "AI status unavailable"
              : usage.enabled
                ? `AI today ${amount(usage.daily_spend)}`
                : "AI disabled · deterministic"}
          </span>
        </div>
        <div
          className="farm-canvas"
          role="region"
          aria-label="Live AI Farm: seven buildings and original animal mascots. Equivalent keyboard controls follow."
        >
          <SceneBoundary onFailure={onFailure}>
            <Scene
              labelPortal={labelPortal}
              states={farm.states}
              motions={farm.motions}
              selected={selected}
              reset={reset}
              onSelect={select}
              regime={
                regime?.data_mode === "stale"
                  ? "UNKNOWN"
                  : (regime?.regime ?? "UNKNOWN")
              }
              simplified={simplified}
              active={active}
              onFailure={onFailure}
              onReady={onReady}
              onMetrics={onMetrics}
              packages={Boolean(
                listings?.some(
                  (l) =>
                    l.active !== false &&
                    !["PASSED", "SOLD", "REMOVED"].includes(l.status ?? ""),
                ),
              )}
              inventory={Boolean(
                farm.get<unknown[]>("/api/marketplace/inventory")?.length,
              )}
            />
          </SceneBoundary>
          <div ref={labelPortal} className="farm-label-layer" />
        </div>
        <div className="farm-controls">
          <span>Drag to orbit · Pinch to zoom</span>
          <button
            onClick={() => {
              close();
              setReset((n) => n + 1);
            }}
          >
            Reset camera
          </button>
          <button
            aria-pressed={simplified}
            onClick={() => setSimplified(!simplified)}
          >
            Simplified scene
          </button>
        </div>
        {farm.simulating && (
          <p className="farm-rehearsal" role="status">
            DEVELOPMENT ONLY · Visual rehearsal, not backend activity
          </p>
        )}
      </div>
      <p className="farm-caption">
        Idle breathing and wind are ambience. Building states come from backend
        data and events.{" "}
        {farm.live.lastHeartbeat
          ? `Last heartbeat at ${new Date(farm.live.lastHeartbeat).toLocaleTimeString()}`
          : "Waiting for heartbeat."}
      </p>
      {Object.values(farm.cache).some((entry) => entry.error) && (
        <p className="farm-fallback" role="status">
          Some feeds are unavailable. Retained figures are last known data, not
          current confirmation.
        </p>
      )}
      <nav className="farm-nav" aria-label="Farm buildings">
        {areas.map((area) => (
          <button
            key={area}
            onClick={() => select(area)}
            aria-pressed={selected === area}
            data-testid={`building-${area}`}
            data-state={farm.states[area]}
          >
            <span
              style={{ background: buildings[area].color }}
              aria-hidden="true"
            />
            <strong>{buildings[area].name}</strong>
            <small>{farm.states[area].replaceAll("_", " ")}</small>
          </button>
        ))}
      </nav>
      {selected && (
        <aside
          ref={panel}
          tabIndex={-1}
          className="farm-detail"
          aria-label={`${buildings[selected].name} details`}
          onKeyDown={(e) => {
            if (e.key === "Escape") close();
          }}
        >
          <header>
            <div>
              <p className="eyebrow">{buildings[selected].subtitle}</p>
              <h2>{buildings[selected].name}</h2>
            </div>
            <button onClick={close} aria-label="Close building details">
              Close ×
            </button>
          </header>
          <p className="farm-state">
            {farm.states[selected].replaceAll("_", " ")}
          </p>
          <BuildingDetails area={selected} />
        </aside>
      )}
      <div className="farm-bottom">
        <section className="farm-ledger">
          <p className="eyebrow">Independent paper portfolios</p>
          {farm.cache["/api/agents"]?.error && (
            <p role="alert">
              Agents unavailable — any values below are last known.
            </p>
          )}
          {farm.agents.map((a) => (
            <Link
              key={a.id}
              href={`/agents/${a.id}`}
              aria-label={`View ${a.name} details`}
            >
              <span>
                {a.name}
                <small>
                  {a.open_positions} open · {a.valuation_state.toUpperCase()}{" "}
                  DATA
                </small>
              </span>
              <strong>
                {amount(a.current_balance)}
                <small>{rate(a.total_return_percent)}</small>
              </strong>
            </Link>
          ))}
          {!farm.agents.length && (
            <p>Waiting for agent data; no balances assumed.</p>
          )}
          <button onClick={() => select("treasury")}>Open treasury →</button>
        </section>
        <section className="farm-ledger">
          <p className="eyebrow">Research & local finds</p>
          {research?.slice(0, 3).map((r) => (
            <Link key={r.id} href={`/research/${r.id}`}>
              <span>
                {r.agent_name} · {r.symbol}
                <small>{r.queue?.status ?? "DISCOVERED"}</small>
              </span>
              <strong>
                {Number(r.score).toFixed(0)}
                <small>score</small>
              </strong>
            </Link>
          ))}
          {!research?.length && (
            <p>No research yet. The farm does not invent opportunities.</p>
          )}
          {farm.agents.map((a) => {
            const intel = farm.get<{ watchlist: string[] }>(
              `/api/agents/${a.id}/intelligence`,
            );
            return (
              <p key={a.id}>
                <small>
                  {a.name} watchlist ·{" "}
                  {intel?.watchlist.join(", ") || "No symbols"}
                </small>
              </p>
            );
          })}
          <button onClick={() => select("marketplace")}>
            Marketplace · {listings?.length ?? "N/A"}
            {listings?.length === 100 ? "+" : ""} recent records →
          </button>
        </section>
        <section className="farm-ledger">
          <p className="eyebrow">Recent activity</p>
          <ul>
            {events?.slice(0, 4).map((e) => (
              <li key={e.id}>
                {eventLink(
                  e,
                  String(
                    e.payload.message ?? e.event_type.replaceAll("_", " "),
                  ),
                )}
              </li>
            ))}
          </ul>
          {!events?.length && <p>A calm start. No recorded activity yet.</p>}
          <button onClick={() => select("research")}>
            Explore intelligence →
          </button>
        </section>
      </div>
      {Simulator && <Simulator metrics={metrics} />}
    </div>
  );
}

function eventLink(e: LiveEvent, label: string) {
  const uuid = /^[0-9a-f-]{36}$/i;
  for (const [key, route] of [
    ["trade_id", "trades"],
    ["candidate_id", "research"],
    ["listing_id", "marketplace"],
  ]) {
    const id = e.payload[key];
    if (typeof id === "string" && uuid.test(id))
      return <Link href={`/${route}/${id}`}>{label}</Link>;
  }
  return <span>{label}</span>;
}

function DataList({ values }: { values: Record<string, unknown> }) {
  return (
    <dl className="farm-facts">
      {Object.entries(values).map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>
            {value == null
              ? "N/A"
              : Array.isArray(value)
                ? value.join(" · ") || "None recorded"
                : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function BuildingDetails({ area }: { area: Area }) {
  const farm = useFarm();
  const research =
    farm.get<Research[]>("/api/research?latest_scan=true&limit=6") ?? [];
  if (area === "agentA" || area === "agentB") {
    const agent = farm.agents.find(
      (a) => a.agent_type === (area === "agentA" ? "equities" : "options"),
    );
    return agent ? (
      <AgentDetails
        agent={agent}
        research={research.filter((r) => r.agent_id === agent.id)}
      />
    ) : (
      <p>Agent data unavailable. No balance assumed.</p>
    );
  }
  if (area === "marketplace") {
    const rows = farm.get<Listing[]>(
      "/api/marketplace/opportunities?limit=100",
    );
    const best = [...(rows ?? [])].sort(
      (a, b) =>
        Number(b.analyses[0]?.analysis.expected_net_profit ?? -Infinity) -
        Number(a.analyses[0]?.analysis.expected_net_profit ?? -Infinity),
    );
    return (
      <>
        <p>
          Packages represent listing research, not purchases. Manual/fixture
          estimates only.
        </p>
        <Link className="farm-detail-link" href="/marketplace">
          Open Marketplace workbench →
        </Link>
        {farm.cache["/api/marketplace/opportunities?limit=100"]?.error && (
          <p role="alert">Listing feed unavailable; last known records.</p>
        )}
        {!rows?.length && <p>No imported listings.</p>}
        {best.slice(0, 5).map((l) => (
          <article key={l.id}>
            <Link href={`/marketplace/${l.id}`}>{l.title} →</Link>
            <DataList
              values={{
                Source: l.source,
                "Estimated net": amount(
                  l.analyses[0]?.analysis.expected_net_profit as string | null,
                ),
                "Sale time": l.analyses[0]?.analysis.expected_sale_time,
                "Distance (miles)": l.details.distance_miles,
                "Risk flags": l.analyses[0]?.analysis.risk_flags,
              }}
            />
          </article>
        ))}
      </>
    );
  }
  if (area === "research" || area === "shadow")
    return (
      <>
        <p>
          {area === "shadow"
            ? "Critique only. Shadow cannot submit orders or control money."
            : "Deterministic research first. AI is optional; animations use zero tokens."}
        </p>
        {research.map((r) => (
          <article key={r.id}>
            <Link href={`/research/${r.id}`}>
              {r.agent_name} · {r.symbol} research →
            </Link>
            <DataList
              values={{
                Score: r.score,
                Status: r.queue?.status,
                AI: r.queue?.ai_status,
                Shadow: r.queue?.shadow_status,
                Risk: r.queue?.risk_status,
                Reason:
                  r.queue?.rejection_reason ||
                  r.rejection_reasons.join("; ") ||
                  r.reasons.join("; "),
              }}
            />
          </article>
        ))}
        {!research.length && <p>No recorded research or reviews yet.</p>}
        {farm.agents.map((a) => {
          const intel = farm.get<{
            watchlist: string[];
            latest_research: Research | null;
          }>(`/api/agents/${a.id}/intelligence`);
          return (
            <article key={a.id}>
              <h3>
                {a.name} {area === "shadow" ? "latest objections" : "watchlist"}
              </h3>
              {area === "shadow" ? (
                <p>
                  {intel?.latest_research?.shadow_reviews
                    ?.map((s) =>
                      String(
                        (s.review.objections as string[] | undefined)?.join(
                          "; ",
                        ),
                      ),
                    )
                    .join("; ") || "No review recorded"}
                </p>
              ) : (
                <p>{intel?.watchlist.join(", ") ?? "Unavailable"}</p>
              )}
            </article>
          );
        })}
      </>
    );
  if (area === "analytics")
    return (
      <>
        {farm.agents.map((a) => {
          const p = farm.get<Performance>(`/api/agents/${a.id}/performance`);
          return (
            <article key={a.id}>
              <Link href={`/agents/${a.id}`}>{a.name} performance →</Link>
              <DataList
                values={{
                  Return: rate(a.total_return_percent),
                  "Max drawdown": rate(p?.max_drawdown_percent),
                  Benchmark: p?.benchmark?.name,
                  "Benchmark return": rate(p?.benchmark?.total_return_percent),
                  "Excess return": rate(p?.benchmark_comparison?.excess_return),
                  "Statistical note": p?.statistics_note,
                }}
              />
            </article>
          );
        })}
        <p>
          Fixtures are not evidence of profitability. Small-sample reliability
          remains N/A.
        </p>
      </>
    );
  const accounts = farm.agents.map((a) =>
    farm.get<Portfolio>(`/api/agents/${a.id}/portfolio`),
  );
  const complete =
    farm.agents.length === 2 &&
    accounts.every(Boolean) &&
    farm.agents.every(
      (a) => !farm.cache[`/api/agents/${a.id}/portfolio`]?.error,
    ) &&
    !farm.cache["/api/agents"]?.error;
  const sum = (key: keyof Portfolio) =>
    complete
      ? accounts.reduce((n, p) => n + Number(p![key]), 0).toFixed(2)
      : null;
  const start = farm.agents.reduce((n, a) => n + Number(a.starting_balance), 0);
  const usage = farm.get<Usage>("/api/ai/usage");
  return (
    <>
      <p>Display-only totals. Accounts remain isolated for all execution.</p>
      <DataList
        values={{
          ...Object.fromEntries(
            farm.agents.map((a) => [a.name, amount(a.current_balance)]),
          ),
          "Combined paper equity": amount(sum("equity")),
          Cash: amount(sum("cash_balance")),
          "Realized P&L": amount(sum("realized_pnl")),
          "Unrealized P&L": amount(sum("unrealized_pnl")),
          "Total paper return":
            complete && start > 0
              ? rate(String((Number(sum("equity")) / start - 1) * 100))
              : "N/A",
          "AI daily / monthly": `${amount(usage?.daily_spend)} / ${amount(usage?.monthly_spend)}`,
          "AI remaining daily / monthly": `${amount(usage?.daily_remaining)} / ${amount(usage?.monthly_remaining)}`,
          Backend: farm.health?.backend,
          Database: farm.health?.database,
          Redis: farm.health?.redis,
          "Event stream": farm.live.status,
        }}
      />
    </>
  );
}

function AgentDetails({
  agent,
  research,
}: {
  agent: Agent;
  research: Research[];
}) {
  const farm = useFarm();
  const positions = farm.get<Position[]>(`/api/agents/${agent.id}/positions`);
  const top = research.find((r) => r.eligible) ?? research[0];
  const contracts = top?.snapshot.ranked_contracts as
    { quote: Record<string, unknown>; eligible: boolean }[] | undefined;
  const contract = contracts?.find((c) => c.eligible)?.quote;
  return (
    <>
      <Link className="farm-detail-link" href={`/agents/${agent.id}`}>
        Open full {agent.name} detail →
      </Link>
      <DataList
        values={{
          Equity: amount(agent.current_balance),
          Return: rate(agent.total_return_percent),
          "Open positions": agent.open_positions,
          "Backend state": agent.status,
          "Data mode": farm.market?.data_state ?? "unavailable",
          "Top opportunity": top?.symbol,
          "Regime / fit": top?.regime,
          Reason: top?.reasons.join("; "),
        }}
      />
      {agent.agent_type === "options" && (
        <DataList
          values={{
            "Selected contract": positions?.[0]?.symbol ?? contract?.symbol,
            DTE: positions?.[0]?.dte ?? contract?.dte,
            Delta: positions?.[0]?.entry_delta ?? contract?.delta,
            "Spread % (candidate)": contract?.spread_percent,
          }}
        />
      )}
      {research.slice(0, 3).map((r) => (
        <p key={r.id}>
          <Link href={`/research/${r.id}`}>
            {r.symbol} · {r.queue?.status} →
          </Link>
        </p>
      ))}
    </>
  );
}
