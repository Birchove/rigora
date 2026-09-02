import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const dbPath = path.join(os.tmpdir(), "research-mentor-e2e.db");
const syncDbUrl = `sqlite:///${dbPath}`;
const asyncDbUrl = `sqlite+aiosqlite:///${dbPath}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  reporter: [["list"], ["junit", { outputFile: "test-results/playwright-junit.xml" }]],
  snapshotPathTemplate: "{testDir}/{testFileName}-snapshots/{arg}-{projectName}-win32{ext}",
  use: {
    baseURL: "http://127.0.0.1:5173",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    trace: "on-first-retry",
  },
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.03,
    },
  },
  webServer: [
    {
      command: `uv run python -c "from sqlalchemy import create_engine; from research_mentor.adapters.sql.base import Base; import research_mentor.adapters.sql.models; e=create_engine('${syncDbUrl}'); Base.metadata.create_all(e)" && uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000`,
      cwd: repoRoot,
      url: "http://127.0.0.1:8000/api/v1/health",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        RESEARCH_MENTOR_MODEL_PROVIDER: "demo",
        RESEARCH_MENTOR_DEMO_MODE: "true",
        RESEARCH_MENTOR_DATABASE_URL: asyncDbUrl,
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
