[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$logDirectory = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'cleanup_legacy_devices.log'
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

$legacyInstanceIds = @(
    'ROOT\HIDCLASS\0001',
    'SWD\SpaceMouseCodex\VID_303A&PID_8360&SPACEMOUSE_CODEX',
    'ROOT\SYSTEM\0002'
)

try {
    foreach ($instanceId in $legacyInstanceIds) {
        if (Get-PnpDevice -InstanceId $instanceId -ErrorAction SilentlyContinue) {
            & pnputil.exe /remove-device $instanceId /force
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to remove legacy device $instanceId (exit $LASTEXITCODE)"
            }
        }
    }

    Write-Host 'Legacy Codex Micro test devices removed.'
} finally {
    Stop-Transcript | Out-Null
}
