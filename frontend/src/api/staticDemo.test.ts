import { describe, expect, it } from "vitest";

import { ApiError } from "./errors";
import { createStaticDemoClient, staticDemoProjects } from "./staticDemo";

describe("static demo client", () => {
  it("lists the three seeded demo stages", async () => {
    const client = createStaticDemoClient();
    const projects = await client.listProjects();
    expect(projects.map((item) => item.project_id)).toEqual([
      "demo-project-planning",
      "demo-project-working",
      "demo-project-validation",
    ]);
    expect(staticDemoProjects()).toHaveLength(3);
  });

  it("rejects writes with a readonly error", async () => {
    const client = createStaticDemoClient();
    await expect(
      client.dispatchCommand("demo-project-planning", {
        type: "run_plan",
        command_id: "c1",
        expected_version: 1,
        mode: "low",
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "static_demo_readonly",
    });
    await expect(client.uploadDocument("demo-project-planning", new File(["x"], "note.txt"))).rejects.toBeInstanceOf(
      ApiError,
    );
  });
});
