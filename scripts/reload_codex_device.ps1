[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$instanceId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX'
$logDirectory = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'reload_codex_device.log'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)

if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $process = Start-Process powershell.exe -ArgumentList $arguments -Verb RunAs -Wait -PassThru
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath
    }
    exit $process.ExitCode
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
try {
    & pnputil.exe /disable-device $instanceId /force
    if ($LASTEXITCODE -ne 0) {
        throw "Device disable failed with exit code $LASTEXITCODE"
    }
    Start-Sleep -Milliseconds 500
    & pnputil.exe /enable-device $instanceId
    if ($LASTEXITCODE -ne 0) {
        throw "Device enable failed with exit code $LASTEXITCODE"
    }
} finally {
    Stop-Transcript | Out-Null
}
