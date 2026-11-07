param([Parameter(Mandatory=$true)][ValidateSet('backend','agent','frontend')][string]$Service)
. "$PSScriptRoot\local-common.ps1"

New-Item -ItemType Directory -Path $StackRuntime -Force | Out-Null
$outLog = Join-Path $StackRuntime "$Service.out.log"
$errLog = Join-Path $StackRuntime "$Service.err.log"
foreach ($path in @($outLog, $errLog)) {
    if (!(Test-Path -LiteralPath $path)) { New-Item -ItemType File -Path $path -Force | Out-Null }
}

$Host.UI.RawUI.WindowTitle = "Law Agent $Service logs"
Write-Host "Following $Service logs. Close this window to stop viewing logs."

$jobs = @(
    Start-Job -ArgumentList $outLog,'OUT' -ScriptBlock {
        param($Path, $Label)
        Get-Content -LiteralPath $Path -Wait -Tail 80 | ForEach-Object { "[$Label] $_" }
    },
    Start-Job -ArgumentList $errLog,'ERR' -ScriptBlock {
        param($Path, $Label)
        Get-Content -LiteralPath $Path -Wait -Tail 80 | ForEach-Object { "[$Label] $_" }
    }
)

try {
    while ($true) {
        foreach ($job in $jobs) { Receive-Job -Job $job }
        Start-Sleep -Milliseconds 300
    }
} finally {
    foreach ($job in $jobs) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}
