param([Parameter(Mandatory=$true)][ValidateSet('backend','agent','frontend')][string]$Service)
. "$PSScriptRoot\local-common.ps1"
try {
    Import-StackEnvironment
    switch ($Service) {
        'backend' {
            Set-Location (Join-Path $StackRoot 'mid-layer')
            & $StackPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
        }
        'agent' {
            Set-Location (Join-Path $StackRoot 'agent-engine')
            & $StackNode 'node_modules/tsx/dist/cli.mjs' watch src/server.ts
        }
        'frontend' {
            Set-Location (Join-Path $StackRoot 'frontend')
            $env:PORT = '3000'
            & $StackNode 'node_modules/next/dist/bin/next' dev --hostname 127.0.0.1 --port 3000
        }
    }
    exit $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
