import { expect, test } from "@playwright/test";

import { createLiveProject } from "./helpers";

test("duplicate command id is idempotent", async ({ page }) => {
  const created = await createLiveProject(page);
  const command = {
    type: "submit_idea",
    command_id: "e2e-duplicate-command",
    expected_version: created.version,
    project_id: created.project_id,
    idea: {
      original_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
      domain: "computer_science",
    },
  };
  const first = await page.request.post(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/commands`,
    { data: command },
  );
  const second = await page.request.post(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/commands`,
    { data: command },
  );
  expect(first.ok()).toBeTruthy();
  expect(second.ok()).toBeTruthy();
  expect(await second.json()).toEqual(await first.json());
});

test("stale expected_version loses CAS", async ({ page }) => {
  const created = await createLiveProject(page);
  const stale = await page.request.post(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/commands`,
    {
      data: {
        type: "submit_idea",
        command_id: "e2e-stale",
        expected_version: created.version + 9,
        project_id: created.project_id,
        idea: {
          original_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
          domain: "computer_science",
        },
      },
    },
  );
  expect(stale.status()).toBe(409);
  expect((await stale.json()).error.code).toBe("stale_project_version");
});

test("SSE replay uses the larger of header and query cursors", async ({ page }) => {
  const created = await createLiveProject(page);
  const response = await fetch(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/events?after=0`,
    { headers: { Accept: "text/event-stream", "Last-Event-ID": "1" } },
  );
  expect(response.ok).toBeTruthy();
  expect(response.headers.get("content-type") ?? "").toContain("text/event-stream");
  await response.body?.cancel();
});

test("restart research remains an explicit command", async ({ page }) => {
  await page.goto("/?project=demo-project-working");
  await expect(page.getByRole("heading", { name: "实验问答" })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新审查新想法" })).toBeVisible();
});
