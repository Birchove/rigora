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
