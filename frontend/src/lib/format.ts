const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function money(value: string | null | undefined): string {
  return value == null ? "—" : usd.format(Number(value));
}

export function percent(value: string): string {
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}
