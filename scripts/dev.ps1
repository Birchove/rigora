$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# uv run uvicorn research_mentor.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
$api = Start-Process -FilePath "uv" -ArgumentList @(
    "run",
    "uvicorn",
    "research_mentor.api.app:create_app",
    "--factory",
    "--reload",
    "--host",
    "127.0.0.1",
    "--port",
    "8000"
) -WorkingDirectory $Root -PassThru

# npm run dev
$web = Start-Process -FilePath "npm" -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "frontend") -PassThru

Write-Host "API worker pid=$($api.Id); Vite pid=$($web.Id)"
try {
    Wait-Process -Id @($api.Id, $web.Id)
}
finally {
    foreach ($process in @($api, $web)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
