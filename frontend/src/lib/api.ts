export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function getJson<T>(
  path: string,
  signal: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(10_000)]),
    cache: "no-store",
  });
  // A degraded health response still contains useful per-service status.
  if (!response.ok && !(path === "/health" && response.status === 503)) {
    throw new Error(
      response.status === 404
        ? "Not found"
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
