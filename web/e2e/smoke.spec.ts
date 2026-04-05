import { test, expect } from "@playwright/test";

test.describe("public marketing + auth entry", () => {
  test("home shows try-first hero, live demo section, and lead form", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: /See the program in action/i,
      }),
    ).toBeVisible();
    await expect(page.getByText("850 Lab").first()).toBeVisible();
    await expect(page.locator("#live-demo")).toBeVisible();
    await expect(page.getByTestId("live-demo-section")).toBeVisible();
    await expect(page.getByTestId("demo-slide-deck")).toBeVisible();
    const run = page.getByRole("button", { name: "Generate demo preview" });
    await expect(run).toBeVisible();
    await expect(page.locator("#lead-form")).toBeVisible();
  });

  test("home: Sign in from top bar; /signup still reachable", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Sign in" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Sign in", exact: true }),
    ).toBeVisible();

    await page.goto("/signup");
    await expect(
      page.getByRole("heading", { name: "Create account", exact: true }),
    ).toBeVisible();
  });

  test("/demo redirects to home with live-demo anchor", async ({ page }) => {
    await page.goto("/demo");
    await expect(page).toHaveURL(/\/(#live-demo)?$/);
    await expect(page.locator("#live-demo")).toBeVisible();
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
