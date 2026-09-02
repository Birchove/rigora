$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

uv lock --check
uv run alembic upgrade head
uv run pytest -q -p no:cacheprovider

Set-Location (Join-Path $Root "frontend")
npm test -- --run
npm run build
npm run e2e -- --project=chromium
