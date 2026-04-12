import { test, expect } from "@playwright/test";

/**
 * Expectations match default production: `VITE_WAITLIST_MODE` unset / not "true"
 * (`WAITLIST_MODE === false` in `src/lib/productGates.ts`).
 * To e2e waitlist mode locally: `VITE_WAITLIST_MODE=true npm run dev` and adjust this file.
 */
test.describe("public marketing + auth entry (guided product / open shell)", () => {
  test("home shows guided hero, live demo, and lead capture form", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("home-hero-headline")).toBeVisible();
    await expect(page.getByTestId("home-hero-headline")).toContainText(
      /story|matters|credit report/i,
    );
    await expect(page.getByText("850 Lab").first()).toBeVisible();
    await expect(page.locator("#live-demo")).toBeVisible();
    await expect(page.getByTestId("live-demo-section")).toBeVisible();
    await expect(page.getByTestId("demo-slide-deck")).toBeVisible();
    const run = page.getByRole("button", { name: "See what shows up" });
    await expect(run).toBeVisible();
    await expect(page.locator("#lead-form")).toBeVisible();
  });

  test("home: Sign in in top bar goes to /login; /signup is reachable", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Sign in" }).first().click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto("/signup");
    await expect(page).toHaveURL(/\/signup$/);
  });

  test("/demo redirects to home with live-demo anchor", async ({ page }) => {
    await page.goto("/demo");
    await expect(page).toHaveURL(/\/(#live-demo)?$/);
    await expect(page.locator("#live-demo")).toBeVisible();
  });

  test("login page loads when signed out", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("forgot-password page remains reachable", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page).toHaveURL(/\/forgot-password$/);
    await expect(
      page.getByRole("heading", { name: "Reset password" }),
    ).toBeVisible();
  });
});

test.describe("guest pre-upload funnel (no session, open shell)", () => {
  test("upload and get-report are reachable", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/\/upload$/);

    await page.goto("/get-report");
    await expect(page).toHaveURL(/\/get-report$/);
  });
});

test.describe("route guards (no session, open shell)", () => {
  test("post-upload funnel redirects to login", async ({ page }) => {
    await page.goto("/payment");
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe("Mission Control shell", () => {
  test("layout, admin key field, and sidebar nav", async ({ page }) => {
    await page.goto("/mission-control");
    await expect(
      page.getByRole("heading", { name: "Mission Control" }),
    ).toBeVisible();
    await expect(
      page.getByPlaceholder("X-Workflow-Admin-Key"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Save" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Architect access" }).click();
    await expect(page).toHaveURL(/\/mission-control\/architect-access$/);

    await page.getByRole("link", { name: "Workflows" }).click();
    await expect(page).toHaveURL(/\/mission-control\/workflows$/);

    await page.getByRole("link", { name: "Exceptions" }).click();
    await expect(page).toHaveURL(/\/mission-control\/exceptions$/);

    await page.getByRole("link", { name: "Responses" }).click();
    await expect(page).toHaveURL(/\/mission-control\/responses$/);

    await page.getByRole("link", { name: "Reminders" }).click();
    await expect(page).toHaveURL(/\/mission-control\/reminders$/);

    await page.getByRole("link", { name: "Admin audit" }).click();
    await expect(page).toHaveURL(/\/mission-control\/audit$/);

    await page.getByRole("link", { name: "Overview" }).click();
    await expect(page).toHaveURL(/\/mission-control$/);
  });
});

test.describe("unknown routes", () => {
  test("wildcard navigates to home", async ({ page }) => {
    await page.goto("/totally-unknown-route-xyz");
    await expect(page).toHaveURL(/\/$/);
  });
});
