param(
    [ValidateSet('Start','Stop','Check','Logs')][string]$Action = 'Start',
    [switch]$ShowLogs
)
. "$PSScriptRoot\local-common.ps1"
$statePath = Join-Path $StackRuntime 'processes.json'
$startedNow = @()

function Read-StackState {
    if (Test-Path -LiteralPath $statePath) {
        return @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
    }
    return @()
}

function Open-ServiceLogWindow([string]$Name) {
    $logScript = Join-Path $PSScriptRoot 'local-logs.ps1'
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',('"' + $logScript + '"'),'-Service',$Name) -WorkingDirectory $StackRoot | Out-Null
}

function Open-StackLogWindows {
    foreach ($serviceName in @('backend','agent','frontend')) { Open-ServiceLogWindow $serviceName }
}

try {
    if ($Action -eq 'Logs') {
        Open-StackLogWindows
        Write-Host 'Opened backend, agent and frontend log windows.'
        exit 0
    }

    if ($Action -eq 'Stop') {
        $entries = @(Read-StackState)
        for ($i = $entries.Count - 1; $i -ge 0; $i--) { Stop-OwnedStackProcess $entries[$i] }
        if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath }
        Write-Host 'Stopped launcher-owned services. PostgreSQL and manually started processes were not changed.'
        exit 0
    }

    $previous = @(Read-StackState)
    foreach ($entry in $previous) {
        $p = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if ($p -and $p.StartTime.ToUniversalTime().ToString('o') -eq $entry.started) {
            throw 'Launcher-owned services are already running. Use stop.cmd before restarting.'
        }
    }
    Import-StackEnvironment
    foreach ($port in @(3000,8000,3100)) {
        if (Test-StackPort $port) { throw "Port $port is in use. Stop the manually started service first; this launcher will not kill it." }
    }
    foreach ($file in @('frontend/node_modules/next/dist/bin/next','agent-engine/node_modules/tsx/dist/cli.mjs')) {
        if (!(Test-Path -LiteralPath (Join-Path $StackRoot $file))) { throw "Missing $file. Run npm ci in that project first." }
    }
    & $StackNode -e 'if(parseInt(process.versions.node,10)<22)process.exit(1)'
    if ($LASTEXITCODE -ne 0) { throw 'Node.js 22 or newer is required.' }
    & $StackPython -c 'import fastapi, uvicorn, sqlalchemy, asyncpg, httpx, jwt, email_validator'
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependencies missing. Set LOCAL_PYTHON to your working interpreter, or install mid-layer with that Python: -m pip install -e ".[dev]"' }
    $databaseCheck = @'
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))
            for table in (
                'users', 'chat_sessions', 'chat_messages', 'user_cases',
                'agent_runs', 'agent_tool_calls', 'agent_run_events',
            ):
                await connection.execute(text('SELECT 1 FROM ' + table + ' LIMIT 0'))
    finally:
        await engine.dispose()
try:
    asyncio.run(asyncio.wait_for(main(), 8))
except Exception as exc:
    print('Database check failed (' + type(exc).__name__ + '). Check PostgreSQL, DATABASE_URL and migrations.')
    raise SystemExit(1)
'@
    & $StackPython -c $databaseCheck
    if ($LASTEXITCODE -ne 0) { throw 'Database is not ready. Start PostgreSQL and, if needed, run alembic upgrade head in the configured backend environment.' }
    if ($Action -eq 'Check') { Write-Host 'Preflight passed. Ready to run start.cmd.'; exit 0 }

    New-Item -ItemType Directory -Path $StackRuntime -Force | Out-Null
    $services = @(
        @{name='backend';url='http://127.0.0.1:8000/health/live'},
        @{name='agent';url='http://127.0.0.1:3100/health'},
        @{name='frontend';url='http://127.0.0.1:3000/login'}
    )
    foreach ($service in $services) {
        Write-Host "Starting $($service.name)..."
        $worker = Join-Path $PSScriptRoot 'local-service.ps1'
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $worker + '"'),'-Service',$service.name) -WindowStyle Hidden -WorkingDirectory $StackRoot -RedirectStandardOutput (Join-Path $StackRuntime "$($service.name).out.log") -RedirectStandardError (Join-Path $StackRuntime "$($service.name).err.log") -PassThru
        $entry = @{name=$service.name;pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o')}
        $startedNow += $entry
        ConvertTo-Json -InputObject @($startedNow) | Set-Content -LiteralPath $statePath -Encoding UTF8
        $healthy = $false
        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline) {
            $process.Refresh()
            if ($process.HasExited) { throw "$($service.name) exited. See .local-run/$($service.name).err.log" }
            try {
                $response = Invoke-WebRequest -Uri $service.url -UseBasicParsing -TimeoutSec 3
                if ($response.StatusCode -eq 200) { $healthy = $true; break }
            } catch { }
            Start-Sleep -Milliseconds 500
        }
        if (!$healthy) { throw "$($service.name) did not become healthy. See .local-run logs." }
        Write-Host "$($service.name) ready."
    }
    Write-Host 'All services ready: http://127.0.0.1:3000'
    Write-Host 'Logs: .local-run/   Stop: double-click stop.cmd'
    if ($ShowLogs) { Open-StackLogWindows }
} catch {
    Write-Host "Startup/stop error: $($_.Exception.Message)" -ForegroundColor Red
    for ($i = $startedNow.Count - 1; $i -ge 0; $i--) {
        try { Stop-OwnedStackProcess $startedNow[$i] } catch { Write-Warning $_.Exception.Message }
    }
    # Keep ownership records after failure so stop.cmd can retry cleanup safely.
    exit 1
}
