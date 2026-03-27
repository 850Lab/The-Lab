import { test, expect } from "@playwright/test";

test.describe("public marketing + auth entry", () => {
  test("home shows hero, brand, and Start now (guests can open funnel)", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: /Turn your credit report into real action/i,
      }),
    ).toBeVisible();
    await expect(page.getByText("850 Lab").first()).toBeVisible();
    const start = page.getByRole("button", { name: "Start now" });
    await expect(start).toBeVisible();
    await expect(start).toBeEnabled();
  });

  test("home links: Sign in and Create account", async ({ page }) => {
    await page.goto("/");
    // TopBar and hero both link to login when signed out.
    await page.getByRole("link", { name: "Sign in" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Sign in", exact: true }),
    ).toBeVisible();

    await page.goto("/");
    await page.getByRole("link", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/signup$/);
    await expect(
      page.getByRole("heading", { name: "Create account", exact: true }),
    ).toBeVisible();
  });

  test("login page form is usable", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("#login-email")).toBeVisible();
    await expect(page.locator("#login-password")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /sign in/i }),
    ).toBeVisible();
  });

  test("signup page form is usable", async ({ page }) => {
    await page.goto("/signup");
    await expect(
      page.getByRole("heading", { name: "Create account", exact: true }),
    ).toBeVisible();
    await expect(page.getByPlaceholder("Email")).toBeVisible();
  });
});

test.describe("guest pre-upload funnel (no session)", () => {
  test("upload shows save-progress prompt, not login wall", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/\/upload$/);
    await expect(
      page.getByRole("heading", { name: /Upload your credit report/i }),
    ).toBeVisible();
    await expect(page.getByText(/Save your progress/i)).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Create account" }).first(),
    ).toBeVisible();
  });

  test("get-report is open without login", async ({ page }) => {
    await page.goto("/get-report");
    await expect(page).toHaveURL(/\/get-report$/);
    await expect(
      page.getByRole("heading", {
        name: /How would you like to get your credit report/i,
      }),
    ).toBeVisible();
  });

  test("Start now navigates to get-report", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Start now" }).click();
    await expect(page).toHaveURL(/\/get-report$/);
  });
});

test.describe("route guards (no session)", () => {
  test("post-upload funnel still requires login", async ({ page }) => {
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
