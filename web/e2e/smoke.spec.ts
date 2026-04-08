import { test, expect } from "@playwright/test";

/**
 * These expectations match `WAITLIST_MODE === true` in `src/lib/productGates.ts`.
 * If you turn waitlist off, update this file accordingly.
 */
test.describe("public marketing + auth entry (waitlist mode)", () => {
  test("home shows waitlist hero and capture form", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("home-hero-headline")).toBeVisible();
    await expect(page.getByTestId("home-hero-headline")).toContainText(/Be first when/i);
    await expect(page.getByText("850 Lab").first()).toBeVisible();
    await expect(page.getByTestId("waitlist-form")).toBeVisible();
    await expect(page.locator("#live-demo")).toHaveCount(0);
  });

  test("home: Waitlist in top bar goes to /waitlist; /signup redirects away", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Waitlist" }).first().click();
    await expect(page).toHaveURL(/\/waitlist$/);

    await page.goto("/signup");
    await expect(page).toHaveURL(/\/waitlist$/);
  });

  test("/demo redirects to waitlist", async ({ page }) => {
    await page.goto("/demo");
    await expect(page).toHaveURL(/\/waitlist$/);
  });

  test("login URL redirects to waitlist when signed out", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/waitlist$/);
  });

  test("forgot-password page remains reachable", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page).toHaveURL(/\/forgot-password$/);
    await expect(
      page.getByRole("heading", { name: "Reset password" }),
    ).toBeVisible();
  });
});

test.describe("guest pre-upload funnel (no session, waitlist mode)", () => {
  test("upload and get-report redirect to waitlist", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/\/waitlist$/);

    await page.goto("/get-report");
    await expect(page).toHaveURL(/\/waitlist$/);
  });
});

test.describe("route guards (no session, waitlist mode)", () => {
  test("post-upload funnel redirects to waitlist", async ({ page }) => {
    await page.goto("/payment");
    await expect(page).toHaveURL(/\/waitlist$/);
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
