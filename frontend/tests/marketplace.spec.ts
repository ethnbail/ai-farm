import { expect, test } from "@playwright/test";

test.beforeEach(() => {
  test.skip(
    process.env.MARKETPLACE_E2E !== "1",
    "Requires a disposable Phase 5 database and local writes",
  );
});
const api = "http://127.0.0.1:8000/api";
const headers = { Origin: "http://localhost:3000" };

test("calibration clearly explains an empty evidence set", async ({ page }) => {
  await page.route("**/api/marketplace/calibration", (route) =>
    route.fulfill({
      json: {
        sample_size: 0,
        hypothetical_sample_size: 0,
        fixture_sample_size: 0,
        status: "insufficient_sample",
      },
    }),
  );
  await page.goto("/marketplace/calibration");
  await expect(
    page.getByText("No completed actual flips yet.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("insufficient_sample", { exact: true }),
  ).toBeVisible();
});

test("preferences, manual listing, observed price update, decisions and actual flip", async ({
  page,
  request,
}) => {
  const before = await (await request.get(`${api}/agents`)).json();
  const external: string[] = [];
  page.on("request", (r) => {
    if (!new URL(r.url()).hostname.match(/^(localhost|127\.0\.0\.1)$/))
      external.push(r.url());
  });
  await page.goto("/marketplace/settings");
  await page.getByLabel("Search ZIP", { exact: true }).fill("94103");
  await page.getByLabel("radius miles", { exact: true }).fill("25");
  await page
    .getByRole("button", { name: "Save Marketplace preferences" })
    .click();
  await expect(page.getByRole("status")).toContainText("Saved");
  await page.goto("/marketplace/new");
  const key = `browser-${Date.now()}`;
  await page.getByLabel("Source listing ID", { exact: false }).fill(key);
  await page
    .getByLabel("Original listing URL", { exact: true })
    .fill(`https://example.com/${key}`);
  await page
    .getByLabel("Title", { exact: true })
    .fill("Observed browser-test console");
  await page.getByLabel("Asking price (USD)", { exact: true }).fill("100");
  await page.getByLabel("Exact model", { exact: true }).fill("TEST console");
  await page.getByLabel("One-way distance (miles)", { exact: true }).fill("5");
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("gaming");
  await page
    .getByLabel("Description", { exact: true })
    .fill("User-provided test evidence. No external contact.");
  await page
    .getByText("Evidence and metadata (optional JSON)", { exact: true })
    .click();
  await page.getByRole("textbox", { name: "comps", exact: true }).fill(
    JSON.stringify(
      [200, 210, 220].map((price) => ({
        price: String(price),
        source: "user supplied test comp",
        observed_at: new Date().toISOString(),
        category: "gaming",
        model: "TEST console",
        condition: "used",
        sold: true,
      })),
    ),
  );
  await page.getByRole("button", { name: "Analyze and save listing" }).click();
  await expect(page).toHaveURL(/\/marketplace\/[0-9a-f-]{36}$/);
  await expect(
    page.getByRole("heading", { name: "Observed browser-test console" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Price history", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Authenticity screening" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "TRACK", exact: true }).click();
  await expect(page.locator(".mp-badge").first()).toContainText("TRACKING");
  await page.getByRole("button", { name: "CONTACTED", exact: true }).click();
  await expect(page.locator(".mp-badge").first()).toContainText("CONTACTED");
  await page.getByRole("button", { name: "Update observed listing" }).click();
  await page.getByLabel("Asking price (USD)", { exact: true }).fill("90");
  await page.getByRole("button", { name: "Save observed update" }).click();
  await expect(page.getByRole("table")).toContainText("$90.00");
  await page.getByRole("button", { name: "Close editor" }).click();
  await page.getByRole("button", { name: "PASS", exact: true }).click();
  await expect(page.locator(".mp-badge").first()).toContainText("PASSED");
  await page
    .getByText("BOUGHT — record completed purchase", { exact: true })
    .click();
  await page.getByLabel("Actual purchase price", { exact: true }).fill("90");
  await page
    .getByLabel("Purchase date/time", { exact: true })
    .fill("2026-01-01T12:00");
  await page
    .getByLabel("I completed this transaction myself", { exact: false })
    .check();
  await page
    .getByRole("button", { name: "Record purchase", exact: true })
    .click();
  await expect(page.locator(".mp-badge").first()).toContainText("BOUGHT");
  await page.getByText("SOLD — record completed sale", { exact: true }).click();
  await page.getByLabel("Actual sale price", { exact: true }).fill("200");
  await page
    .getByLabel("Sale date/time", { exact: true })
    .fill("2026-01-11T12:00");
  await page.getByLabel("platform fees", { exact: true }).fill("20");
  await page
    .getByLabel("I completed this transaction myself", { exact: false })
    .check();
  await page.getByRole("button", { name: "Record sale", exact: true }).click();
  await expect(page.locator(".mp-badge").first()).toContainText("SOLD");
  const id = page.url().split("/").at(-1);
  const outcome = await (
    await request.get(`${api}/marketplace/listings/${id}`)
  ).json();
  expect(outcome.outcome.outcome.net_profit).toBe("90.00");
  expect(outcome.outcome.outcome.days_to_sell).toBe(10);
  expect(await (await request.get(`${api}/agents`)).json()).toEqual(before);
  expect(external).toEqual([]);
  await page.screenshot({
    path: test.info().outputPath("marketplace-detail.png"),
    fullPage: true,
  });
});

test("JSON and CSV import report partial errors and dry-run does not save", async ({
  page,
  request,
}) => {
  const before = await (
    await request.get(`${api}/marketplace/listings`)
  ).json();
  await page.goto("/marketplace/import");
  const row = {
    source_listing_id: `dry-${Date.now()}`,
    source_url: "https://example.com/manual",
    title: "Dry run listing",
    asking_price: "80",
  };
  await page
    .getByRole("textbox", { name: "Import content", exact: true })
    .fill(JSON.stringify([row, { title: "invalid" }]));
  await page.getByRole("button", { name: "Run import", exact: true }).click();
  await expect(
    page.getByText("Per-row results", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/row: 2/)).toBeVisible();
  expect(
    (await (await request.get(`${api}/marketplace/listings`)).json()).total,
  ).toBe(before.total);
  await page
    .getByRole("combobox", { name: "Format", exact: true })
    .selectOption("csv");
  await page
    .getByRole("textbox", { name: "Import content", exact: true })
    .fill(
      `source_listing_id,source_url,title,asking_price\ncsv-${Date.now()},https://example.com/csv,CSV browser listing,70\n`,
    );
  await page.getByLabel("Dry run", { exact: false }).uncheck();
  await page.getByRole("button", { name: "Run import", exact: true }).click();
  await expect(page.getByText(/title: CSV browser listing/)).toBeVisible();
});

test("URL workflow explicitly requires manual details; sorting and mobile pages work", async ({
  page,
}) => {
  await page.goto("/marketplace/import");
  await page
    .getByLabel("Listing URL", { exact: true })
    .fill("https://example.com/user-reference");
  await page.getByRole("button", { name: "Use URL as reference" }).click();
  await expect(
    page.getByText("No data was extracted.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Original listing URL", { exact: true }),
  ).toHaveValue("https://example.com/user-reference");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/marketplace");
  await page
    .getByRole("combobox", { name: "Sort by", exact: true })
    .selectOption("profit");
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("gaming");
  await expect(
    page.getByRole("heading", { name: "Observed browser-test console →" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("marketplace-mobile.png"),
    fullPage: true,
  });
  await page.goto("/marketplace/inventory");
  await expect(
    page.getByRole("heading", { name: "What’s on the shelf." }),
  ).toBeVisible();
  await page.goto("/marketplace/calibration");
  await expect(
    page.getByText("insufficient_sample", { exact: true }),
  ).toBeVisible();
});

test("real Marketplace SSE reaches the existing farm with zero AI calls", async ({
  page,
  request,
}) => {
  const before = await (await request.get(`${api}/ai/usage`)).json();
  await page.goto("/");
  await expect(page.getByTestId("realtime-status")).toHaveText("Live");
  await expect(page.getByTestId("farm-stage")).toHaveAttribute(
    "data-renderer",
    "ready",
    { timeout: 30000 },
  );
  await page.evaluate(() => {
    const w = window as unknown as { marketEvents: string[] };
    w.marketEvents = [];
    window.addEventListener("ai-farm:event", (e) =>
      w.marketEvents.push((e as CustomEvent).detail.event_type),
    );
  });
  const response = await request.post(`${api}/marketplace/dev/fixture`, {
    headers,
  });
  expect(response.ok()).toBeTruthy();
  const report = await response.json();
  const id = report.results[0].id;
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { marketEvents: string[] }).marketEvents,
      ),
    )
    .toContain("marketplace_opportunity_created");
  await request.post(`${api}/marketplace/dev/price-drop`, {
    headers,
    data: { listing_id: id },
  });
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { marketEvents: string[] }).marketEvents,
      ),
    )
    .toContain("marketplace_price_drop");
  await expect(page.getByTestId("building-marketplace")).toHaveAttribute(
    "data-state",
    "ANALYZING",
  );
  await request.post(`${api}/marketplace/listings/${id}/pass`, {
    headers,
    data: {},
  });
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { marketEvents: string[] }).marketEvents,
      ),
    )
    .toContain("marketplace_listing_passed");
  await request.post(`${api}/marketplace/dev/sale`, {
    headers,
    data: { listing_id: id },
  });
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { marketEvents: string[] }).marketEvents,
      ),
    )
    .toContain("marketplace_item_sold");
  await expect(page.getByTestId("building-marketplace")).toHaveAttribute(
    "data-state",
    "SUCCESS",
  );
  expect((await (await request.get(`${api}/ai/usage`)).json()).calls).toBe(
    before.calls,
  );
  await page.screenshot({
    path: test.info().outputPath("marketplace-farm-sale.png"),
    fullPage: true,
  });
});
