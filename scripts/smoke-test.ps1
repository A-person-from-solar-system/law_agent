$ErrorActionPreference = "Stop"

$agentToken = if ($env:AGENT_ENGINE_SERVICE_TOKEN) {
    $env:AGENT_ENGINE_SERVICE_TOKEN
} else {
    "local-agent-service-token"
}

$null = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
$null = Invoke-RestMethod -Uri "http://127.0.0.1:3100/health"
$frontend = Invoke-WebRequest -Uri "http://127.0.0.1:3000/login" -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "Frontend health check failed" }

$request = @{
    requestId = "smoke-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    sessionId = "smoke-session"
    prompt = "请检索房屋租赁欠付租金的法律依据"
    history = @()
} | ConvertTo-Json -Depth 10

$response = Invoke-WebRequest `
    -Uri "http://127.0.0.1:3100/internal/v1/agent/runs" `
    -Method Post `
    -Headers @{ Authorization = "Bearer $agentToken"; Accept = "text/event-stream" } `
    -ContentType "application/json" `
    -Body $request `
    -UseBasicParsing

if ($response.Content -notmatch "event: run.completed") {
    throw "Agent stream did not complete"
}
if ($response.Content -notmatch "mock-statute-001") {
    throw "Agent did not retrieve evidence through the Python knowledge API"
}

Write-Host "Smoke test passed: frontend -> Python gateway -> Agent engine -> Python knowledge API."
