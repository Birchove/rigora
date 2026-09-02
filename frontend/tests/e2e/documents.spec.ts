import { expect, test } from "@playwright/test";

import { createLiveProject } from "./helpers";

test("supported markdown upload is accepted", async ({ page }) => {
  const created = await createLiveProject(page);
  const response = await page.request.post(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/documents`,
    {
      multipart: {
        file: {
          name: "notes.md",
          mimeType: "text/markdown",
          buffer: Buffer.from("# 实验记录\n分层压缩基线。\n"),
        },
      },
    },
  );
  expect(response.ok()).toBeTruthy();
});

test("journal export endpoints share JSON and markdown", async ({ page }) => {
  const json = await page.request.get(
    "http://127.0.0.1:8000/api/v1/projects/demo-project-working/journal.json",
  );
  const markdown = await page.request.get(
    "http://127.0.0.1:8000/api/v1/projects/demo-project-working/journal.md",
  );
  expect(json.ok()).toBeTruthy();
  expect(markdown.ok()).toBeTruthy();
  expect(await markdown.text()).toContain("研究");
});
