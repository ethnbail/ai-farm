"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Badge, ConnectionNotice, Metric } from "@/components/ui";
import { useResource } from "@/hooks/use-resource";
import { money, percent } from "@/lib/format";
import type { LiveEvent, MarketStatus, Position, Trade } from "@/lib/types";

export const timestamp = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : "N/A";
export const price = (value: string | null | undefined) =>
  value == null ? "N/A" : `$${Number(value).toFixed(4)}`;
export const rate = (value: string | null | undefined) =>
  value == null ? "N/A" : percent(value);
export const amount = (value: string | null | undefined) =>
  value == null ? "N/A" : money(value);

export function MarketBanner() {
  const { data, error } = useResource<MarketStatus>("/api/market/status");
  return (
    <section
      className="mb-5 rounded-2xl border border-line px-5 py-4"
      aria-label="Paper trading environment"
    >
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <strong className="text-green">PAPER TRADING</strong>
        <Badge>
          {error
            ? "UNAVAILABLE DATA"
            : `${(data?.data_state ?? "unavailable").toUpperCase()} DATA`}
        </Badge>
        <span className="text-muted">
          US market: {data?.session.replaceAll("_", " ") ?? "checking"}
        </span>
        {data && !data.execution_enabled && (
          <span role="alert">Execution disabled</span>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">
        Simulated funds and fills only. No brokerage connection.{" "}
        {data?.provider === "mock" &&
          "Prices and Greeks are fixed test fixtures, not live quotes."}
      </p>
      <ConnectionNotice error={error} />
    </section>
  );
}

export function RecentActivity() {
  const { data, error } = useResource<LiveEvent[]>("/api/activity?limit=8");
  return (
    <section className="panel mt-5" aria-labelledby="activity-title">
      <h2 id="activity-title" className="text-xl font-semibold">
        Recent Activity
      </h2>
      <ConnectionNotice error={error} />
      {data?.length === 0 && (
        <p className="mt-4 text-sm text-muted">
          No activity yet. The paper worker is opt-in.
        </p>
      )}
      {!data && !error && <p className="mt-4 text-muted">Loading activity…</p>}
      <ol className="mt-4 divide-y divide-line">
        {data?.map((event) => (
          <li
            key={event.id}
            className="flex flex-wrap justify-between gap-2 py-3 text-sm"
          >
            <span>
              {String(
                event.payload.message ?? event.event_type.replaceAll("_", " "),
              )}
            </span>
            <time className="text-xs text-muted" dateTime={event.created_at}>
              {timestamp(event.created_at)}
            </time>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function DataTable({
  headers,
  children,
  label,
}: {
  headers: string[];
  children: ReactNode;
  label: string;
}) {
  return (
    <div
      className="mt-5 max-w-full overflow-x-auto"
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      <table className="w-full text-left text-sm">
        <thead>
          <tr>
            {headers.map((header) => (
              <th
                key={header}
                className="whitespace-nowrap border-b border-line p-3 font-medium"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Positions({ id }: { id: string }) {
  const { data, error } = useResource<Position[]>(
    `/api/agents/${id}/positions`,
  );
  return (
    <section className="panel mt-5" aria-labelledby="positions-title">
      <h2 id="positions-title" className="text-xl font-semibold">
        Open positions
      </h2>
      <ConnectionNotice error={error} />
      {!data && !error && <p className="mt-4 text-muted">Loading positions…</p>}
      {data?.length === 0 && (
        <p className="mt-5 text-muted">
          No open positions. NO_TRADE is a valid risk decision.
        </p>
      )}
      {data?.map((p) => (
        <article
          key={p.id}
          className="mt-5 rounded-2xl border border-line p-5"
          data-testid="position"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="min-w-0 break-all font-semibold">
              <Link
                className="text-green hover:underline"
                href={`/trades/${p.trade_id}`}
              >
                {p.symbol}
              </Link>
            </h3>
            <Badge>{p.data_state.toUpperCase()} DATA</Badge>
          </div>
          <p className="mt-2 text-sm text-muted">
            {p.company_name} · Opened {timestamp(p.opened_at)}
          </p>
          <dl className="mt-5 grid grid-cols-2 gap-5 md:grid-cols-4">
            <Metric
              label={p.asset_type === "option" ? "Contracts" : "Quantity"}
              value={p.quantity}
            />
            <Metric label="Entry price" value={price(p.average_entry_price)} />
            <Metric label="Current bid mark" value={price(p.current_price)} />
            <Metric label="Market value" value={money(p.market_value)} />
            <Metric label="Stop loss" value={price(p.stop_loss)} />
            <Metric label="Take profit" value={price(p.take_profit)} />
            <Metric label="Unrealized P&L" value={money(p.unrealized_pnl)} />
            <Metric label="Return" value={rate(p.return_percent)} />
            {p.asset_type === "option" && (
              <>
                <Metric
                  label="Underlying / type"
                  value={`${p.underlying_symbol} ${p.option_type}`}
                />
                <Metric label="Strike" value={money(p.strike)} />
                <Metric
                  label="Expiration / DTE"
                  value={`${p.expiration} / ${p.dte}`}
                />
                <Metric
                  label="Bid / ask"
                  value={`${price(p.bid)} / ${price(p.ask)}`}
                />
                <Metric label="Entry IV" value={p.entry_iv ?? "N/A"} />
                <Metric label="Entry delta" value={p.entry_delta ?? "N/A"} />
                <Metric label="Entry theta" value={p.entry_theta ?? "N/A"} />
              </>
            )}
          </dl>
          <p className="mt-4 text-xs text-muted">
            Quote timestamp: {timestamp(p.data_timestamp)}. Marks exclude exit
            slippage. Entry Greeks are recorded snapshots.
          </p>
        </article>
      ))}
    </section>
  );
}

export function TradeHistory({ id }: { id: string }) {
  const { data, error } = useResource<Trade[]>(`/api/agents/${id}/trades`);
  return (
    <section className="panel mt-5" aria-labelledby="trade-history">
      <h2 id="trade-history" className="text-xl font-semibold">
        Trade history
      </h2>
      <ConnectionNotice error={error} />
      {!data && !error && (
        <p className="py-8 text-muted">Loading trade history…</p>
      )}
      {data?.length === 0 && (
        <div className="py-12 text-center">
          <h3 className="text-xl font-medium">No trades yet</h3>
          <p className="mt-2 text-sm text-muted">
            Approved paper trades and their reasoning will appear here.
          </p>
        </div>
      )}
      {!!data?.length && (
        <>
          <p className="mt-3 text-xs text-muted">
            Most recent 50 trades. Select a symbol to inspect its recorded
            replay.
          </p>
          <DataTable
            label="Trade history table"
            headers={[
              "Date",
              "Company / ticker / contract",
              "Side",
              "Quantity",
              "Entry",
              "Stop",
              "Target",
              "Exit",
              "P&L $",
              "P&L %",
              "Status / exit reason",
            ]}
          >
            {data.map((t) => (
              <tr key={t.id} className="border-b border-line">
                <td className="p-3 whitespace-nowrap">
                  {timestamp(t.entry_time)}
                </td>
                <td className="p-3">
                  <Link
                    className="font-medium text-green hover:underline"
                    href={`/trades/${t.id}`}
                  >
                    {t.symbol}
                  </Link>
                  <span className="block text-muted">{t.company_name}</span>
                  {t.asset_type === "option" && (
                    <span className="block whitespace-nowrap text-xs">
                      {String(t.entry_snapshot?.underlying_symbol ?? "—")}{" "}
                      {String(t.entry_snapshot?.option_type ?? "—")} · Strike{" "}
                      {String(t.entry_snapshot?.strike ?? "—")} ·{" "}
                      {String(t.entry_snapshot?.expiration ?? "—")}
                    </span>
                  )}
                </td>
                <td className="p-3">{t.side}</td>
                <td className="p-3">{t.quantity}</td>
                <td className="p-3">{price(t.entry_price)}</td>
                <td className="p-3">{price(t.stop_loss)}</td>
                <td className="p-3">{price(t.take_profit)}</td>
                <td className="p-3">{price(t.exit_price)}</td>
                <td className="p-3 whitespace-nowrap">
                  {amount(t.realized_pnl)}
                </td>
                <td className="p-3">{rate(t.realized_return_percent)}</td>
                <td className="p-3">
                  {t.status}
                  <span className="block text-muted">
                    {t.exit_reason?.replaceAll("_", " ") ?? "—"}
                  </span>
                </td>
              </tr>
            ))}
          </DataTable>
        </>
      )}
    </section>
  );
}
