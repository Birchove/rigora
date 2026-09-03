import { expect, test } from "@playwright/test";

test("desktop and narrow layouts match reviewed snapshots", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?project=demo-project-working");
  await expect(page.getByRole("heading", { name: "实验问答" })).toBeVisible();
  await expect(page).toHaveScreenshot("workspace-desktop.png", { animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".sidebar-toggle")).toBeVisible();
  await expect(page).toHaveScreenshot("workspace-mobile.png", { animations: "disabled" });
});

test("dark workspace uses the dark lockup and forest surfaces", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("rigora-theme", "dark");
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?project=demo-project-working");
  await expect(page.getByRole("heading", { name: "实验问答" })).toBeVisible();
  await expect(page.locator(".brand-lockup")).toHaveAttribute(
    "src",
    /rigora-lockup-dark\.svg/,
  );
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page).toHaveScreenshot("workspace-desktop-dark.png", { animations: "disabled" });
});
