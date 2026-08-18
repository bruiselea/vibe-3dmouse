[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$logDirectory = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'create_swdevice.log'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -PassThru -Wait
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath
    }
    exit $process.ExitCode
}

$workspace = Split-Path -Parent $PSScriptRoot
$creator = Join-Path $workspace 'native\swdevice_creator\x64\Release\swdevice_creator.exe'
if (-not (Test-Path -LiteralPath $creator)) {
    throw "Software-device helper was not built: $creator"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
try {
    $ErrorActionPreference = 'Continue'
    $output = & $creator 2>&1
    $creatorExitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    $output | Set-Content -LiteralPath $logPath -Encoding utf8
    if ($creatorExitCode -ne 0) {
        throw "Software device creation failed with exit code $creatorExitCode"
    }
    Add-Content -LiteralPath $logPath -Value 'Software-enumerated Codex Micro device created.' -Encoding utf8
} catch {
    Add-Content -LiteralPath $logPath -Value ($_ | Out-String) -Encoding utf8
    exit 1
}
