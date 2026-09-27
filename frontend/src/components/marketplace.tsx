"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { API_URL } from "@/lib/api";
import { useResource } from "@/hooks/use-resource";
import { amount } from "@/components/trading";

type Data = Record<string, unknown>;
interface Listing {
  id: string;
  title: string;
  source: string;
  source_listing_id: string;
  source_url: string;
  asking_price: string;
  status: string;
  active: boolean;
  listed_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  listing_age_minutes: number;
  details: Data;
  analysis: Data | null;
  price_history?: { id: string; price: string; observed_at: string }[];
  comps?: { id: string; evidence: Data }[];
  outcome?: { outcome: Data } | null;
  inventory?: { purchase: Data; sold: boolean } | null;
  duplicate_of_listing_id?: string;
}
function object(value: unknown): Data {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Data)
    : {};
}
function label(key: string) {
  return key.replaceAll("_", " ");
}
function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unknown";
  if (Array.isArray(value))
    return value.length ? value.map(display).join(" · ") : "None recorded";
  if (typeof value === "object")
    return Object.entries(object(value))
      .map(([k, v]) => `${label(k)}: ${display(v)}`)
      .join("; ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}
function money(value: unknown) {
  return amount(value == null ? null : String(value));
}
function probability(value: unknown) {
  return value == null ? "Unknown" : `${(Number(value) * 100).toFixed(0)}%`;
}
function ErrorNotice({ error }: { error?: string }) {
  return error ? (
    <p role="alert" className="mp-notice">
      {error}. Retained records may be outdated.
    </p>
  ) : null;
}
function Facts({ value }: { value: Data }) {
  return (
    <dl className="mp-facts">
      {Object.entries(value).map(([key, v]) => (
        <div key={key}>
          <dt>{label(key)}</dt>
          <dd>{display(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mp-block">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function Shell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="marketplace">
      <nav className="mp-nav" aria-label="Marketplace navigation">
        <Link href="/">← Farm</Link>
        <Link href="/marketplace">Opportunities</Link>
        <Link href="/marketplace/new">Add listing</Link>
        <Link href="/marketplace/import">Import</Link>
        <Link href="/marketplace/inventory">Inventory</Link>
        <Link href="/marketplace/calibration">Calibration</Link>
        <Link href="/marketplace/settings">Preferences</Link>
      </nav>
      <header className="mp-heading">
        <p className="eyebrow">LOCAL FINDS · HUMAN DECISIONS</p>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </header>
      <p className="mp-safety">
        Research and recordkeeping only. You contact sellers and arrange
        purchases yourself. No messaging, payment or purchase automation. Agent
        A/B paper funds are separate.
      </p>
      {children}
    </div>
  );
}
async function write(path: string, payload: unknown, method = "POST") {
  const response = await fetch(`${API_URL}/api/marketplace${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(20000),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map((e: Data) => `${display(e.loc)}: ${display(e.msg)}`)
              .join("; ")
          : `Request failed (${response.status})`,
    );
  window.dispatchEvent(new Event("ai-farm:update"));
  return data;
}
function useWrite() {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function perform(path: string, payload: unknown, method = "POST") {
    setBusy(true);
    setMessage("");
    try {
      const result = await write(path, payload, method);
      setMessage("Saved. No external action was taken.");
      return result;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save");
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, message, perform };
}
const categories = [
  "gaming",
  "laptop",
  "camera",
  "phone",
  "luxury",
  "sneakers",
  "furniture",
  "bicycle",
  "heater",
  "air_conditioner",
  "fitness",
  "collectible",
  "unknown",
];

export function MarketplaceDashboard() {
  const [sort, setSort] = useState("score"),
    [category, setCategory] = useState(""),
    [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const query = `/api/marketplace/listings?sort=${sort}&category=${encodeURIComponent(category)}&status=${status}&offset=${offset}&limit=20`;
  const listings = useResource<{ items: Listing[]; total: number }>(query);
  const metrics = useResource<Data>("/api/marketplace/performance");
  const notices = useResource<
    { id: string; message: string; severity: string }[]
  >("/api/marketplace/notifications");
  const m = metrics.data ?? {};
  return (
    <Shell
      title="The trading post."
      subtitle="Fresh opportunities, grounded estimates, and room for your judgment."
    >
      <ErrorNotice error={listings.error || metrics.error} />
      <section className="mp-metrics" aria-label="Marketplace metrics">
        {[
          ["Active tracked", m.active_tracked_listings],
          ["Strong candidates", m.strong_candidates],
          ["Inventory", m.inventory_count],
          ["Capital tied up", money(m.capital_tied_up)],
          ["Expected inventory profit", money(m.expected_inventory_profit)],
          ["Realized profit", money(m.realized_profit)],
          ["Average days to sell", m.average_days_to_sell],
          ["Calibration", object(m.calibration).status],
        ].map(([name, value]) => (
          <div key={String(name)}>
            <span>{String(name)}</span>
            <strong>{display(value)}</strong>
          </div>
        ))}
      </section>
      <div className="mp-toolbar">
        <label>
          Sort by
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setOffset(0);
            }}
          >
            {[
              "score",
              "freshness",
              "profit",
              "roi",
              "sell_through",
              "sale_time",
              "distance",
            ].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Category
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All records</option>
            {[
              "NEW",
              "TRACKING",
              "REVIEWING",
              "CONTACTED",
              "BOUGHT",
              "PASSED",
              "SOLD",
              "EXPIRED",
              "REMOVED",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <Link className="mp-button primary" href="/marketplace/new">
          Add a listing
        </Link>
      </div>
      {!listings.data ? (
        <p>Loading observed listings…</p>
      ) : !listings.data.items.length ? (
        <Block title="A clear counter.">
          <p>
            No listings match yet. Add a listing or import your own export. We
            never fabricate opportunities.
          </p>
        </Block>
      ) : (
        <div className="mp-listings">
          {listings.data.items.map((row) => {
            const a = row.analysis ?? {},
              sell = object(a.sell_through);
            return (
              <article className="mp-listing" key={row.id}>
                <div className="mp-listing-top">
                  <span className="mp-badge">
                    {row.source === "fixture"
                      ? "FICTIONAL FIXTURE"
                      : row.source}{" "}
                    · {row.status}
                  </span>
                  <span>{display(a.tier)}</span>
                </div>
                <Link href={`/marketplace/${row.id}`}>
                  <h2>{row.title} →</h2>
                </Link>
                <p>
                  {display(object(a.freshness).bucket)} ·{" "}
                  {Math.round(row.listing_age_minutes)} min old ·{" "}
                  {display(row.details.distance_miles)} miles one way
                </p>
                <Facts
                  value={{
                    asking: money(row.asking_price),
                    resale: `${money(a.expected_resale_low)} – ${money(a.expected_resale_high)}`,
                    expected_net: money(a.expected_net_profit),
                    ROI:
                      a.roi_percent == null ? "Unknown" : `${a.roi_percent}%`,
                    sell_through_30d: probability(
                      sell.sell_through_probability_30d,
                    ),
                    sale_time: a.expected_sale_time,
                    score: a.opportunity_score,
                  }}
                />
                {row.duplicate_of_listing_id && (
                  <p className="mp-notice">
                    Likely repost — not a new opportunity.
                  </p>
                )}
                <p className="mp-muted">{display(a.risk_flags)}</p>
              </article>
            );
          })}
        </div>
      )}
      <div className="mp-toolbar">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous
        </button>
        <span>{listings.data?.total ?? 0} records</span>
        <button
          disabled={offset + 20 >= (listings.data?.total ?? 0)}
          onClick={() => setOffset(offset + 20)}
        >
          Next
        </button>
      </div>
      <Block title="Activity at the stall">
        <ErrorNotice error={notices.error} />
        <ul className="mp-activity">
          {notices.data?.slice(0, 8).map((n) => (
            <li key={n.id}>
              <span className="mp-badge">{n.severity}</span> {n.message}
            </li>
          ))}
        </ul>
        {!notices.data?.length && <p>No Marketplace notifications yet.</p>}
      </Block>
    </Shell>
  );
}

type FieldSpec = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  hint?: string;
};
const listingFields: FieldSpec[] = [
  { name: "source", label: "Source", required: true },
  {
    name: "source_listing_id",
    label: "Source listing ID",
    hint: "Leave blank to assign a local ID",
  },
  {
    name: "source_url",
    label: "Original listing URL",
    type: "url",
    required: true,
  },
  { name: "title", label: "Title", required: true },
  {
    name: "asking_price",
    label: "Asking price (USD)",
    type: "number",
    required: true,
  },
  {
    name: "original_price",
    label: "Original advertised price (USD)",
    type: "number",
  },
  { name: "brand", label: "Brand" },
  { name: "model", label: "Exact model" },
  { name: "condition", label: "Condition", required: true },
  { name: "location_text", label: "Location" },
  { name: "zip_code", label: "ZIP code" },
  { name: "distance_miles", label: "One-way distance (miles)", type: "number" },
  {
    name: "driving_minutes_round_trip",
    label: "Round-trip driving minutes",
    type: "number",
  },
  { name: "listed_at", label: "Listed date/time", type: "datetime-local" },
  { name: "seller_id", label: "Seller source ID" },
  { name: "seller_name", label: "Seller display name" },
  { name: "seller_rating", label: "Seller rating (0–5)", type: "number" },
  { name: "seller_review_count", label: "Seller review count", type: "number" },
  { name: "seller_joined_date", label: "Seller joined date", type: "date" },
  { name: "shipping_cost", label: "Expected shipping (USD)", type: "number" },
  {
    name: "repair_cost",
    label: "Repair/cleaning estimate (USD)",
    type: "number",
  },
  { name: "other_costs", label: "Other expected costs (USD)", type: "number" },
];
function localDate(value: unknown) {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function Fields({
  fields,
  defaults = {},
}: {
  fields: FieldSpec[];
  defaults?: Data;
}) {
  return (
    <>
      {fields.map((f) => (
        <label key={f.name}>
          {f.label}
          <input
            name={f.name}
            type={f.type ?? "text"}
            required={f.required}
            min={f.type === "number" ? 0 : undefined}
            step={f.type === "number" ? "any" : undefined}
            defaultValue={
              f.type === "datetime-local"
                ? localDate(defaults[f.name])
                : defaults[f.name] == null
                  ? ""
                  : String(defaults[f.name])
            }
          />
          {f.hint && <small>{f.hint}</small>}
        </label>
      ))}
    </>
  );
}

function ListingForm({
  initial,
  reference,
}: {
  initial?: Listing;
  reference?: string;
}) {
  const router = useRouter(),
    action = useWrite(),
    identity = useRef(initial?.source_listing_id ?? "");
  const [parseError, setParseError] = useState("");
  const defaults: Data = {
    source: "manual",
    condition: "used",
    shipping_cost: "0",
    repair_cost: "0",
    other_costs: "0",
    ...initial?.details,
    ...(initial
      ? {
          source: initial.source,
          source_listing_id: initial.source_listing_id,
          source_url: initial.source_url,
          title: initial.title,
          asking_price: initial.asking_price,
        }
      : {}),
    ...(reference ? { source_url: reference } : {}),
  };
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setParseError("");
    const fd = new FormData(e.currentTarget),
      data: Data = {};
    for (const f of listingFields) {
      const v = String(fd.get(f.name) ?? "").trim();
      if (v)
        data[f.name] =
          f.type === "datetime-local" ? new Date(v).toISOString() : v;
    }
    identity.current = String(
      data.source_listing_id || identity.current || crypto.randomUUID(),
    );
    data.source_listing_id = identity.current;
    data.description = fd.get("description");
    data.category = fd.get("category");
    data.notes = fd.get("notes");
    data.active = fd.get("active") === "on";
    for (const key of [
      "comps",
      "demand",
      "item_metadata",
      "image_metadata",
      "seller_profile_metadata",
    ]) {
      const raw = String(fd.get(key) || "");
      if (raw.trim()) {
        try {
          data[key] = JSON.parse(raw);
        } catch {
          setParseError(`${label(key)} must contain valid JSON`);
          return;
        }
      }
    }
    const result = await action.perform(
      initial ? `/listings/${initial.id}` : "/listings",
      data,
      initial ? "PUT" : "POST",
    );
    if (result) router.push(`/marketplace/${result.id}`);
  }
  return (
    <form className="mp-form" onSubmit={submit}>
      <div className="mp-fields">
        <Fields fields={listingFields} defaults={defaults} />
        <label>
          Category
          <select
            name="category"
            defaultValue={String(defaults.category ?? "unknown")}
          >
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Description
        <textarea
          name="description"
          rows={4}
          maxLength={5000}
          defaultValue={String(defaults.description ?? "")}
        />
      </label>
      <label>
        Private notes
        <textarea
          name="notes"
          rows={2}
          maxLength={2000}
          defaultValue={String(defaults.notes ?? "")}
        />
      </label>
      <label className="mp-check">
        <input
          type="checkbox"
          name="active"
          defaultChecked={initial?.active ?? true}
        />
        Listing is currently active (user observation)
      </label>
      <details>
        <summary>Evidence and metadata (optional JSON)</summary>
        <p>
          No comps means no resale estimate. Sold comps alone do not establish
          sell-through. Supply a complete cohort including unsold listings for
          demand estimates.
        </p>
        {[
          "comps",
          "demand",
          "item_metadata",
          "image_metadata",
          "seller_profile_metadata",
        ].map((key) => (
          <label key={key}>
            {label(key)}
            <textarea
              name={key}
              rows={4}
              placeholder={
                key === "item_metadata"
                  ? '{"accessories":{"controller":true,"power cable":true,"HDMI cable":true}}'
                  : key === "comps"
                    ? '[{"price":"300","source":"my sold comp","observed_at":"2026-01-01T12:00:00Z","category":"gaming","model":"Exact model","condition":"used","sold":true}]'
                    : key === "demand"
                      ? '[{"source":"my complete cohort","observed_at":"2026-01-01T12:00:00Z","market":"LOCAL","cohort_size":100,"observation_days":30,"sold_7d":20,"sold_14d":40,"sold_30d":60}]'
                      : ""
              }
              defaultValue={
                defaults[key] ? JSON.stringify(defaults[key], null, 2) : ""
              }
            />
          </label>
        ))}
        <p>
          Use only permitted source data. Do not paste cookies, credentials,
          private messages, phone numbers or raw page HTML. Image URLs are
          references; no vision analysis is configured.
        </p>
      </details>
      <p role="status">{parseError || action.message}</p>
      <button className="primary" disabled={action.busy}>
        {action.busy
          ? "Saving…"
          : initial
            ? "Save observed update"
            : "Analyze and save listing"}
      </button>
    </form>
  );
}
export function MarketplaceNew() {
  return (
    <Shell
      title="Bring a find to the counter."
      subtitle="Paste what you observed. Leave unknown details blank."
    >
      <Block title="Manual listing">
        <ListingForm />
      </Block>
    </Shell>
  );
}

export function MarketplaceImport() {
  const action = useWrite();
  const [report, setReport] = useState<Data | null>(null),
    [reference, setReference] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget),
      format = String(fd.get("format"));
    const raw = String(fd.get("content"));
    let payload: Data;
    try {
      payload =
        format === "json"
          ? { listings: JSON.parse(raw), dry_run: fd.get("dry_run") === "on" }
          : { content: raw, dry_run: fd.get("dry_run") === "on" };
    } catch {
      setReport({ error: "Invalid JSON. Use an array of listing objects." });
      return;
    }
    const value = await action.perform(`/import/${format}`, payload);
    if (value) setReport(value);
  }
  return (
    <Shell
      title="Your sources. One workbench."
      subtitle="Manual capture, supplied exports and safe URL references. No scraping or credential access."
    >
      <Block title="Start with a URL">
        <form
          className="mp-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const url = String(new FormData(e.currentTarget).get("url"));
            const result = await action.perform("/import/url", { url });
            if (result) {
              setReference(result.source_url);
              try {
                sessionStorage.setItem(
                  "ai-farm:marketplace-url",
                  result.source_url,
                );
              } catch {}
            }
          }}
        >
          <label>
            Listing URL
            <input name="url" type="url" required />
          </label>
          <button disabled={action.busy}>Use URL as reference</button>
        </form>
        {reference && (
          <>
            <p className="mp-notice">
              No data was extracted. Complete the required listing fields below.
            </p>
            <ListingForm key={reference} reference={reference} />
          </>
        )}
      </Block>
      <Block title="Import CSV or JSON">
        <form className="mp-form" onSubmit={submit}>
          <div className="mp-fields">
            <label>
              Format
              <select name="format">
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
              </select>
            </label>
            <label>
              Load file (max 1 MB)
              <input
                type="file"
                accept=".json,.csv,application/json,text/csv"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (file.size > 1_000_000) {
                    setReport({ error: "File exceeds 1 MB" });
                    return;
                  }
                  const input = e.currentTarget.form?.elements.namedItem(
                    "content",
                  ) as HTMLTextAreaElement | null;
                  if (input) input.value = await file.text();
                }}
              />
            </label>
          </div>
          <label>
            Import content
            <textarea
              name="content"
              rows={10}
              required
              defaultValue={
                '[{"source":"manual","source_listing_id":"my-listing-1","source_url":"https://example.com/listing","title":"My observed listing","asking_price":"80"}]'
              }
            />
          </label>
          <label className="mp-check">
            <input name="dry_run" type="checkbox" defaultChecked />
            Dry run — validate and analyze without saving
          </label>
          <button disabled={action.busy}>Run import</button>
        </form>
        <p role="status">{action.message}</p>
        {report && (
          <div role="status">
            <Facts
              value={{
                dry_run: report.dry_run,
                created: report.created,
                updated: report.updated,
                error: report.error,
              }}
            />
            <h3>Per-row results</h3>
            <ul>
              {Array.isArray(report.results) &&
                report.results.map((r, i) => <li key={i}>{display(r)}</li>)}
              {Array.isArray(report.errors) &&
                report.errors.map((r, i) => (
                  <li key={i} className="mp-notice">
                    {display(r)}
                  </li>
                ))}
            </ul>
          </div>
        )}
      </Block>
      <ConnectorStatus />
    </Shell>
  );
}
function ConnectorStatus() {
  const { data, error } = useResource<Data[]>(
    "/api/marketplace/connectors/status",
  );
  return (
    <Block title="Connector capabilities">
      <ErrorNotice error={error} />
      {data?.map((c) => (
        <article key={String(c.id)}>
          <h3>
            {display(c.id)} · {display(c.status)}
          </h3>
          <p>{display(c.description)}</p>
          <p className="mp-muted">
            Automatic refresh: {display(c.supports_refresh)} · Manual update
            required: {display(c.requires_manual_update)}
          </p>
        </article>
      ))}
    </Block>
  );
}

const settingFields: FieldSpec[] = [
  { name: "zip_code", label: "Search ZIP" },
  ...[
    "radius_miles",
    "min_asking_price",
    "max_asking_price",
    "min_expected_profit",
    "min_roi_percent",
    "max_pickup_miles",
    "max_pickup_time_minutes",
    "max_listing_age_hours",
    "min_seller_rating",
    "cost_per_mile",
    "platform_fee_percent",
    "payment_fee_percent",
    "risk_buffer_percent",
    "strong_score_threshold",
    "stale_after_hours",
  ].map((name) => ({ name, label: label(name), type: "number" })),
];
function SettingsForm({ data }: { data: Data }) {
  const action = useWrite();
  return (
    <form
      className="mp-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget),
          value: Data = {};
        for (const f of settingFields) {
          const v = String(fd.get(f.name) || "").trim();
          if (v) value[f.name] = v;
          else if (
            [
              "zip_code",
              "max_pickup_time_minutes",
              "max_listing_age_hours",
              "min_seller_rating",
            ].includes(f.name)
          )
            value[f.name] = null;
        }
        for (const name of ["preferred_categories", "excluded_categories"])
          value[name] = String(fd.get(name) || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        for (const name of ["freshness_minutes", "inventory_days"])
          value[name] = String(fd.get(name) || "")
            .split(",")
            .map(Number);
        value.hemisphere = fd.get("hemisphere");
        await action.perform("/settings", value, "PUT");
      }}
    >
      {!data.writes_enabled && (
        <p className="mp-notice">
          Writes are disabled. Restart the local backend with
          LOCAL_WRITES_ENABLED=true to save user-controlled changes. Keep the
          application local.
        </p>
      )}
      <div className="mp-fields">
        <Fields fields={settingFields} defaults={data} />
        {[
          "preferred_categories",
          "excluded_categories",
          "freshness_minutes",
          "inventory_days",
        ].map((name) => (
          <label key={name}>
            {label(name)} (comma-separated)
            <input
              name={name}
              defaultValue={
                Array.isArray(data[name]) ? data[name].join(", ") : ""
              }
            />
          </label>
        ))}
        <label>
          Climate hemisphere
          <select name="hemisphere" defaultValue={String(data.hemisphere)}>
            <option>unknown</option>
            <option>northern</option>
            <option>southern</option>
          </select>
        </label>
      </div>
      <p>
        No precise location is collected automatically. Mileage is a user
        estimate, not a route calculation; its cost includes fuel. Thresholds
        must be strictly increasing.
      </p>
      <p role="status">{action.message}</p>
      <button className="primary" disabled={action.busy}>
        Save Marketplace preferences
      </button>
    </form>
  );
}
export function MarketplaceSettings() {
  const { data, error } = useResource<Data>("/api/marketplace/settings");
  return (
    <Shell
      title="Define your search."
      subtitle="Keep distance, costs and evidence standards under your control."
    >
      <ErrorNotice error={error} />
      <Block title="Search & economics">
        {data ? <SettingsForm data={data} /> : <p>Loading preferences…</p>}
      </Block>
      <ConnectorStatus />
    </Shell>
  );
}

export function MarketplaceListingDetail({ id }: { id: string }) {
  const { data, error } = useResource<Listing>(
      `/api/marketplace/listings/${id}`,
    ),
    action = useWrite();
  const [edit, setEdit] = useState(false),
    [photos, setPhotos] = useState(false);
  const a = data?.analysis ?? {},
    d = data?.details ?? {};
  return (
    <Shell
      title={data?.title ?? "Opening listing…"}
      subtitle="Evidence, assumptions and your next decision, in one place."
    >
      <ErrorNotice error={error} />
      {data && (
        <>
          <div className="mp-toolbar">
            <span className="mp-badge">
              {data.source === "fixture" ? "FICTIONAL FIXTURE" : data.source} ·{" "}
              {data.status}
            </span>
            <a
              className="mp-button"
              href={data.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Open original listing ↗
            </a>
            <button onClick={() => setEdit(!edit)}>
              {edit ? "Close editor" : "Update observed listing"}
            </button>
          </div>
          {edit && (
            <Block title="Manual refresh">
              <p>
                There is no continuous source monitoring. Save only newly
                observed information.
              </p>
              <ListingForm initial={data} />
            </Block>
          )}
          <section className="mp-metrics" aria-label="Listing economics">
            {[
              ["Asking", money(data.asking_price)],
              ["Conservative resale", money(a.conservative_resale_value)],
              ["Expected net", money(a.expected_net_profit)],
              ["ROI", a.roi_percent == null ? "Unknown" : `${a.roi_percent}%`],
              ["Target buy", money(a.target_buy_price)],
              ["Maximum / walk away", money(a.max_buy_price)],
            ].map(([k, v]) => (
              <div key={String(k)}>
                <span>{k}</span>
                <strong>{display(v)}</strong>
              </div>
            ))}
          </section>
          {a.version !== "phase5-v1" && Object.keys(a).length > 0 && (
            <Block title="Preserved prior-phase estimate">
              <p>
                Historical supplied estimates, not verified sold comparables.
                Add current evidence before relying on Phase 5 recommendations.
              </p>
              <Facts value={a} />
            </Block>
          )}
          <Block title="Your decision">
            <p>
              These buttons only record your decision. “Contacted” does not send
              a message. Record purchases or sales only after you have completed
              them yourself.
            </p>
            <form className="mp-form" onSubmit={(e) => e.preventDefault()}>
              <label>
                Decision notes
                <input name="notes" defaultValue={String(d.notes ?? "")} />
              </label>
              <label className="mp-check">
                <input
                  name="would"
                  type="checkbox"
                  defaultChecked={Boolean(d.would_have_bought)}
                />
                Would have bought (hypothetical tracking, separate from actual
                flips)
              </label>
              <div className="mp-toolbar">
                {[
                  ["track", "TRACK"],
                  ["contacted", "CONTACTED"],
                  ["pass", "PASS"],
                ].map(([event, text]) => (
                  <button
                    key={event}
                    disabled={
                      action.busy || ["BOUGHT", "SOLD"].includes(data.status)
                    }
                    onClick={async (e) => {
                      const fd = new FormData(e.currentTarget.form!);
                      await action.perform(`/listings/${id}/${event}`, {
                        notes: fd.get("notes"),
                        would_have_bought: fd.get("would") === "on",
                      });
                    }}
                  >
                    {text}
                  </button>
                ))}
              </div>
            </form>
            <p role="status">{action.message}</p>
            {!data.inventory ? (
              <OutcomeForm key="purchase" id={id} kind="bought" />
            ) : !data.inventory.sold ? (
              <OutcomeForm key="sale" id={id} kind="sold" />
            ) : (
              <p>
                Sale recorded. Actual results appear in inventory/performance.
              </p>
            )}
          </Block>
          <div className="mp-two">
            <Block title="Observed listing">
              <p>{display(d.description)}</p>
              <Facts
                value={{
                  category: d.category,
                  condition: d.condition,
                  model: d.model,
                  location: d.location_text,
                  ZIP: d.zip_code,
                  age_minutes: Math.round(data.listing_age_minutes),
                  listed_at: data.listed_at,
                  first_seen: data.first_seen_at,
                  last_seen: data.last_seen_at,
                  status: data.status,
                  active: data.active,
                  refresh: "Manual update required",
                  notes: d.notes,
                }}
              />
              {Array.isArray(d.image_metadata) &&
                d.image_metadata.length > 0 && (
                  <>
                    <button onClick={() => setPhotos(!photos)}>
                      {photos ? "Hide photos" : "Load source-provided photos"}
                    </button>
                    {photos && (
                      <div className="mp-photos">
                        {d.image_metadata.map((image, i) => {
                          const v = object(image);
                          return typeof v.url === "string" ? (
                            <a
                              key={i}
                              href={v.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={v.url}
                                alt={String(
                                  v.caption ??
                                    `Supplied listing photo ${i + 1}`,
                                )}
                                loading="lazy"
                                referrerPolicy="no-referrer"
                              />
                            </a>
                          ) : null;
                        })}
                      </div>
                    )}
                    <p>
                      Images load only on request. Vision analysis unavailable.
                    </p>
                  </>
                )}
            </Block>
            <Block title="Price history">
              <p>Observed prices, not inferred historical sales.</p>
              <table>
                <thead>
                  <tr>
                    <th>Observed</th>
                    <th>Asking price</th>
                  </tr>
                </thead>
                <tbody>
                  {data.price_history?.map((h) => (
                    <tr key={h.id}>
                      <td>{new Date(h.observed_at).toLocaleString()}</td>
                      <td>{money(h.price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Facts value={object(a.price_history_summary)} />
              {data.duplicate_of_listing_id && (
                <Link href={`/marketplace/${data.duplicate_of_listing_id}`}>
                  Likely repost of earlier listing →
                </Link>
              )}
            </Block>
          </div>
          <Block title="Evidence behind the resale range">
            <Facts
              value={{
                low: money(a.expected_resale_low),
                high: money(a.expected_resale_high),
                median: money(a.median_comp),
                comp_count: a.comp_count,
                recency_days: a.comp_recency_days,
                quality: a.comp_quality,
                confidence: a.valuation_confidence,
                sources: a.sources,
              }}
            />
            {data.comps?.map((c) => (
              <details key={c.id}>
                <summary>
                  {money(c.evidence.price)} · {display(c.evidence.source)}
                </summary>
                <Facts value={c.evidence} />
              </details>
            ))}
            <CompForm
              id={id}
              category={String(d.category ?? "unknown")}
              model={String(d.model ?? "")}
              condition={String(d.condition ?? "used")}
            />
          </Block>
          <div className="mp-two">
            {[
              ["Sell-through (not guaranteed)", a.sell_through],
              ["Sale-time windows", a.sale_time],
              ["Local vs national demand", a.demand],
              ["Seasonality", a.seasonality],
              ["Seller motivation", a.seller_motivation],
              ["Seller reliability", a.seller_reliability],
              ["Completeness", a.completeness],
              ["Authenticity screening", a.counterfeit],
              ["Travel economics", a.travel],
              ["Transparent ranking", a.scoring],
            ].map(([title, value]) => (
              <Block key={String(title)} title={String(title)}>
                <Facts value={object(value)} />
              </Block>
            ))}
          </div>
          <Block title="Costs, confidence and cautions">
            <Facts
              value={{
                risk_flags: a.risk_flags,
                reasons: a.reasoning,
                fees: money(a.estimated_fees),
                shipping: money(a.shipping_cost),
                repairs: money(a.repair_cost),
                other_costs: money(a.other_costs),
                risk_buffer: money(a.risk_buffer),
                break_even: money(a.break_even_resale_price),
                profit_per_day: a.profit_per_expected_day_held,
                profit_per_mile: a.profit_per_mile,
                profit_per_pickup_hour: a.profit_per_hour,
                confidence: a.confidence,
                data_quality: a.data_quality,
                AI: a.ai_status,
                vision: a.vision_status,
                explanation: a.explanation,
              }}
            />
          </Block>
          <Block title="Recorded outcome">
            {data.outcome ? (
              <Facts value={data.outcome.outcome} />
            ) : (
              <p>No purchase or sale outcome recorded.</p>
            )}
          </Block>
          {data.status === "PASSED" && Boolean(d.would_have_bought) && (
            <HypotheticalForm id={id} />
          )}
        </>
      )}
    </Shell>
  );
}

function OutcomeForm({ id, kind }: { id: string; kind: "bought" | "sold" }) {
  const action = useWrite();
  const fields: FieldSpec[] =
    kind === "bought"
      ? [
          {
            name: "purchase_price",
            label: "Actual purchase price",
            type: "number",
            required: true,
          },
          {
            name: "purchase_date",
            label: "Purchase date/time",
            type: "datetime-local",
            required: true,
          },
          ...["travel_cost", "repair_cost", "other_costs"].map((name) => ({
            name,
            label: label(name),
            type: "number",
          })),
        ]
      : [
          {
            name: "sale_price",
            label: "Actual sale price",
            type: "number",
            required: true,
          },
          {
            name: "sale_date",
            label: "Sale date/time",
            type: "datetime-local",
            required: true,
          },
          { name: "selling_platform", label: "Selling platform" },
          ...[
            "platform_fees",
            "shipping_cost",
            "payment_fees",
            "other_costs",
          ].map((name) => ({ name, label: label(name), type: "number" })),
        ];
  return (
    <details>
      <summary>
        {kind === "bought"
          ? "BOUGHT — record completed purchase"
          : "SOLD — record completed sale"}
      </summary>
      <form
        className="mp-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget),
            value: Data = {};
          for (const f of fields) {
            const v = String(fd.get(f.name) || "");
            if (v)
              value[f.name] =
                f.type === "datetime-local" ? new Date(v).toISOString() : v;
          }
          value.notes = fd.get("notes");
          if (kind === "sold")
            value.authenticity_outcome = fd.get("authenticity_outcome");
          await action.perform(`/listings/${id}/${kind}`, value);
        }}
      >
        <div className="mp-fields">
          <Fields fields={fields} />
          {kind === "sold" && (
            <label>
              Known authenticity outcome
              <select name="authenticity_outcome">
                <option>unknown</option>
                <option>authentic</option>
                <option>counterfeit</option>
              </select>
            </label>
          )}
        </div>
        <label>
          Outcome notes
          <textarea name="notes" rows={2} />
        </label>
        <label className="mp-check">
          <input required type="checkbox" />I completed this transaction myself;
          this only records it.
        </label>
        <p role="status">{action.message}</p>
        <button className="primary" disabled={action.busy}>
          {kind === "bought" ? "Record purchase" : "Record sale"}
        </button>
      </form>
    </details>
  );
}
function CompForm({
  id,
  category,
  model,
  condition,
}: {
  id: string;
  category: string;
  model: string;
  condition: string;
}) {
  const action = useWrite();
  return (
    <details>
      <summary>Add a manually observed comparable</summary>
      <form
        className="mp-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          const value: Data = {
            category,
            model: model || null,
            condition,
            sold: fd.get("sold") === "on",
            quality: "user_reported",
            market: fd.get("market"),
          };
          for (const key of ["price", "source", "source_url", "days_to_sell"]) {
            if (fd.get(key)) value[key] = fd.get(key);
          }
          value.observed_at = new Date(
            String(fd.get("observed_at")),
          ).toISOString();
          await action.perform(`/listings/${id}/comps`, value);
        }}
      >
        <div className="mp-fields">
          <Fields
            fields={[
              {
                name: "price",
                label: "Comparable price",
                type: "number",
                required: true,
              },
              { name: "source", label: "Evidence source", required: true },
              { name: "source_url", label: "Evidence URL", type: "url" },
              {
                name: "observed_at",
                label: "Observed date/time",
                type: "datetime-local",
                required: true,
              },
              {
                name: "days_to_sell",
                label: "Observed days to sell",
                type: "number",
              },
            ]}
          />
          <label>
            Comparable market
            <select name="market">
              <option>UNKNOWN</option>
              <option>LOCAL</option>
              <option>NATIONAL</option>
            </select>
          </label>
        </div>
        <label className="mp-check">
          <input type="checkbox" name="sold" defaultChecked />
          This is a sold comp, not an asking-price listing
        </label>
        <p>
          Matched category/model/condition: {category} / {model || "unknown"} /{" "}
          {condition}. Evidence is user-reported, not independently verified.
        </p>
        <p role="status">{action.message}</p>
        <button disabled={action.busy}>Add comparable</button>
      </form>
    </details>
  );
}
function HypotheticalForm({ id }: { id: string }) {
  const action = useWrite();
  return (
    <Block title="Would-have-bought observation">
      <p>
        Hypothetical evidence never counts as actual profit or an actual flip.
      </p>
      <form
        className="mp-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget),
            value: Data = { sold: fd.get("sold") === "on" };
          for (const name of [
            "actual_sale_price",
            "days_to_sell",
            "observation_days",
            "source",
          ]) {
            if (fd.get(name)) value[name] = fd.get(name);
          }
          await action.perform(`/listings/${id}/hypothetical`, value);
        }}
      >
        <div className="mp-fields">
          <Fields
            fields={[
              {
                name: "actual_sale_price",
                label: "Later observed sale price",
                type: "number",
              },
              {
                name: "days_to_sell",
                label: "Observed days to sell",
                type: "number",
              },
              {
                name: "observation_days",
                label: "Complete observation days",
                type: "number",
                required: true,
              },
              {
                name: "source",
                label: "Outcome evidence source",
                required: true,
              },
            ]}
          />
        </div>
        <label className="mp-check">
          <input type="checkbox" name="sold" />A later sale was actually
          observed
        </label>
        <p role="status">{action.message}</p>
        <button disabled={action.busy}>Save hypothetical evidence</button>
      </form>
    </Block>
  );
}

export function MarketplaceInventory() {
  const { data, error } = useResource<Data[]>("/api/marketplace/inventory"),
    action = useWrite();
  return (
    <Shell
      title="What’s on the shelf."
      subtitle="Human-recorded purchases, capital committed and time held. Suggestions never take action."
    >
      <ErrorNotice error={error} />
      <div className="mp-toolbar">
        <button
          disabled={action.busy}
          onClick={() => action.perform("/inventory/refresh", {})}
        >
          Refresh aging & observed unsold outcomes
        </button>
        <span role="status">{action.message}</span>
      </div>
      {!data?.length ? (
        <Block title="Nothing on the shelf yet.">
          <p>Inventory appears only after you record a completed purchase.</p>
        </Block>
      ) : (
        <div className="mp-listings">
          {data.map((item) => (
            <Block key={String(item.id)} title={String(item.title)}>
              <Link href={`/marketplace/${item.listing_id}`}>Open item →</Link>
              <Facts
                value={{
                  source: object(item.purchase).source,
                  purchase_price: money(object(item.purchase).purchase_price),
                  capital_tied_up: money(object(item.purchase).cost_basis),
                  estimated_resale: money(item.estimated_resale_value),
                  unrealized_estimated_profit: money(item.expected_profit),
                  days_held: item.days_held,
                  aging: item.aging_status,
                  expected_sale_window: item.expected_sale_window,
                  suggestions: item.suggestions,
                }}
              />
            </Block>
          ))}
        </div>
      )}
    </Shell>
  );
}
export function MarketplaceCalibration() {
  const { data, error } = useResource<Data>("/api/marketplace/calibration");
  return (
    <Shell
      title="Learn from what happened."
      subtitle="Prediction errors, not promises. Actual flips and hypothetical observations stay separate."
    >
      <ErrorNotice error={error} />
      <Block title="Calibration status">
        <Facts
          value={{
            sample_size: data?.sample_size,
            hypothetical_sample_size: data?.hypothetical_sample_size,
            excluded_fixture_sample_size: data?.fixture_sample_size,
            status: data?.status,
            explanation: data?.explanation,
          }}
        />
        {!data?.sample_size && (
          <p>
            No completed actual flips yet. There is not enough evidence for
            calibration conclusions.
          </p>
        )}
      </Block>
      <div className="mp-two">
        {["resale", "profit", "sale_time", "probabilities", "bias_by"].map(
          (key) => (
            <Block key={key} title={label(key)}>
              <Facts value={object(data?.[key])} />
            </Block>
          ),
        )}
      </div>
    </Shell>
  );
}
