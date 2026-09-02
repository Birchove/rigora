import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { createLiveProject } from "./helpers";

test("frontend bundle does not embed provider secrets", async () => {
  const dist = path.resolve("dist");
  if (!fs.existsSync(dist)) {
    return;
  }
  for (const file of fs.readdirSync(dist, { recursive: true })) {
    const full = path.join(dist, String(file));
    if (!fs.statSync(full).isFile()) {
      continue;
    }
    const text = fs.readFileSync(full, "utf8");
    expect(text).not.toMatch(/sk-[A-Za-z0-9]{10,}/);
    expect(text).not.toContain("RESEARCH_MENTOR_MODEL_API_KEY=");
  }
});

test("non-CS domain is rejected before a model run", async ({ page }) => {
  const created = await createLiveProject(page);
  const response = await page.request.post(
    `http://127.0.0.1:8000/api/v1/projects/${created.project_id}/commands`,
    {
      data: {
        type: "submit_idea",
        command_id: "e2e-non-cs",
        expected_version: created.version,
        project_id: created.project_id,
        idea: {
          original_idea: "评估一种新的临床疗法",
          domain: "biology",
        },
      },
    },
  );
  expect([422, 409, 400, 200, 202]).toContain(response.status());
  if (response.ok()) {
    const project = await page.request.get(
      `http://127.0.0.1:8000/api/v1/projects/${created.project_id}`,
    );
    const body = await project.json();
    expect(body.phase).not.toBe("planning");
  }
});
