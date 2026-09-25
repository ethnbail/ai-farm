import type { ReactNode } from "react";

export function Icon({
  kind = "sprout",
  className = "",
}: {
  kind?: "sprout" | "field" | "sun" | "basket" | "arrow";
  className?: string;
}) {
  const paths = {
    sprout: (
      <>
        <path d="M12 21v-9M12 15C5 15 3 10 3 5c6 0 9 3 9 8M12 12c0-6 3-9 9-9 0 6-3 9-9 9" />
      </>
    ),
    field: (
      <>
        <path d="M3 20h18M5 16V9m7 7V4m7 12v-5M3 6l4-3 5 4 7-5" />
      </>
    ),
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
      </>
    ),
    basket: (
      <>
        <path d="M3 9h18l-2 12H5L3 9Zm4 0 5-7 5 7M9 13v4m6-4v4" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  };
  return (
    <svg
      aria-hidden="true"
      className={className}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[kind]}
    </svg>
  );
}

export function Badge({
  children,
  active = false,
}: {
  children: ReactNode;
  active?: boolean;
}) {
  return (
    <span className={`badge ${active ? "badge-green" : ""}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}

export function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-2 break-words text-xl font-medium tabular-nums">
        {value}
      </dd>
    </div>
  );
}

export function ConnectionNotice({ error }: { error?: string }) {
  if (!error) return null;
  return (
    <p role="alert" className="notice">
      Could not refresh: {error}. Any displayed values may be out of date.
      Retrying automatically.
    </p>
  );
}
