$ErrorActionPreference = 'Stop'
$StackRoot = Split-Path $PSScriptRoot -Parent
$StackRuntime = Join-Path $StackRoot '.local-run'

function Import-StackEnvironment {
    $config = Join-Path $StackRoot '.env.local'
    if (!(Test-Path -LiteralPath $config)) {
        throw 'Missing root .env.local. Copy scripts/local.env.example to .env.local and configure DATABASE_URL.'
    }
    foreach ($line in Get-Content -LiteralPath $config -Encoding UTF8) {
        $value = $line.Trim()
        if (!$value -or $value.StartsWith('#')) { continue }
        if ($value -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { throw 'Invalid entry in root .env.local: expected KEY=VALUE.' }
        $key = $Matches[1]
        $entry = $Matches[2].Trim()
        if ($entry.Length -ge 2 -and (($entry.StartsWith('"') -and $entry.EndsWith('"')) -or ($entry.StartsWith("'") -and $entry.EndsWith("'")))) {
            $entry = $entry.Substring(1, $entry.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($key, $entry, 'Process')
    }
    if (!$env:DATABASE_URL -or $env:DATABASE_URL.Contains('CHANGE_ME')) { throw 'Set DATABASE_URL in root .env.local to your existing PostgreSQL database.' }
    if (!$env:JWT_SECRET -or !$env:INTERNAL_SERVICE_TOKEN -or !$env:AGENT_ENGINE_SERVICE_TOKEN) { throw 'JWT_SECRET and both internal service tokens are required in root .env.local.' }
    $script:StackPython = $env:LOCAL_PYTHON
    if (!$script:StackPython) { $script:StackPython = Join-Path $StackRoot 'mid-layer\.venv\Scripts\python.exe' }
    if (!(Test-Path -LiteralPath $script:StackPython)) { throw 'Python not found. Set LOCAL_PYTHON in root .env.local to the interpreter used by your backend.' }
    $script:StackPython = (Resolve-Path -LiteralPath $script:StackPython).Path
    $script:StackNode = (Get-Command node.exe -ErrorAction Stop).Source
    # The launcher owns local wiring; provider/model settings still load from agent-engine/.env.
    $env:HOST = '127.0.0.1'
    $env:PORT = '3100'
    $env:AGENT_ENGINE_BASE_URL = 'http://127.0.0.1:3100'
    $env:KNOWLEDGE_BASE_URL = 'http://127.0.0.1:8000'
    if (!$env:KNOWLEDGE_BACKEND) { $env:KNOWLEDGE_BACKEND = 'rag' }
    if (!$env:RAG_BASE_URL) { $env:RAG_BASE_URL = 'http://127.0.0.1:8001' }
    if (!$env:RAG_MODE) { $env:RAG_MODE = 'hybrid' }
    if (!$env:RAG_TIMEOUT_SECONDS) { $env:RAG_TIMEOUT_SECONDS = '60' }
    if (!$env:TOOL_TIMEOUT_MS) { $env:TOOL_TIMEOUT_MS = '65000' }
    if (!$env:RUN_TIMEOUT_MS) { $env:RUN_TIMEOUT_MS = '180000' }
    $env:BACKEND_API_URL = 'http://127.0.0.1:8000'
    $env:NEXT_PUBLIC_API_BASE_URL = '/backend'
    $env:PYTHONUNBUFFERED = '1'
    $env:PYTHONIOENCODING = 'utf-8'
}

function Test-StackPort([int]$Port) {
    $socket = New-Object Net.Sockets.TcpClient
    try {
        $task = $socket.ConnectAsync('127.0.0.1', $Port)
        return ($task.Wait(500) -and $socket.Connected)
    } catch { return $false } finally { $socket.Dispose() }
}

function Stop-OwnedStackProcess($Entry) {
    $process = Get-Process -Id $Entry.pid -ErrorAction SilentlyContinue
    if (!$process) { return }
    if ($process.StartTime.ToUniversalTime().ToString('o') -ne $Entry.started) {
        throw "PID $($Entry.pid) has been reused; refusing to stop an unrelated process."
    }
    & taskkill.exe /PID $Entry.pid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not stop owned service $($Entry.name)." }
}
