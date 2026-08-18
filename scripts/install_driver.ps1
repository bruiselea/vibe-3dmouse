[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'
$installLogDirectory = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex'
$installLogPath = Join-Path $installLogDirectory 'install_driver.log'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    New-Item -ItemType Directory -Path $installLogDirectory -Force | Out-Null
    Remove-Item -LiteralPath $installLogPath -Force -ErrorAction SilentlyContinue
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Configuration $Configuration"
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -PassThru -Wait
    if (Test-Path -LiteralPath $installLogPath) {
        Get-Content -LiteralPath $installLogPath
    }
    exit $process.ExitCode
}

New-Item -ItemType Directory -Path $installLogDirectory -Force | Out-Null
Start-Transcript -LiteralPath $installLogPath -Force | Out-Null
trap {
    Write-Error ($_ | Out-String)
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

$workspace = Split-Path -Parent $PSScriptRoot
$output = Join-Path $workspace "native\vhidmini2\driver\umdf2\x64\$Configuration"
$package = Join-Path $output 'VhidminiUm'
$inf = Join-Path $package 'VhidminiUm.inf'
$certificate = Join-Path $output 'CodexMicroHid.cer'
$swDeviceScript = Join-Path $workspace 'scripts\create_swdevice.ps1'
$controlDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$controlFile = Join-Path $controlDirectory 'control.bin'
$codexInstanceId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX'

foreach ($path in @($inf, $certificate, $swDeviceScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file was not found: $path"
    }
}

Import-Certificate -FilePath $certificate -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null
Import-Certificate -FilePath $certificate -CertStoreLocation 'Cert:\LocalMachine\TrustedPublisher' | Out-Null

New-Item -ItemType Directory -Path $controlDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $controlFile)) {
    [IO.File]::WriteAllBytes($controlFile, [byte[]]::new(68))
} else {
    $stream = [IO.File]::Open($controlFile, 'Open', 'ReadWrite', 'ReadWrite')
    try {
        if ($stream.Length -lt 68) {
            $stream.SetLength(68)
        }
    } finally {
        $stream.Dispose()
    }
}
& icacls.exe $controlDirectory /grant '*S-1-5-32-545:(OI)(CI)M' /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to grant control-channel access (exit $LASTEXITCODE)"
}

$existingCodexDevice = Get-PnpDevice -InstanceId $codexInstanceId -ErrorAction SilentlyContinue
$codexDeviceIsPresent = $false
if ($existingCodexDevice) {
    $isPresentProperty = Get-PnpDeviceProperty -InstanceId $codexInstanceId `
        -KeyName 'DEVPKEY_Device_IsPresent' -ErrorAction SilentlyContinue
    $codexDeviceIsPresent = $isPresentProperty.Data -eq $true
}
$deviceNeedsReboot = $false

# Older builds installed the same HID package as a ROOT device.  Leaving one
# started publishes a second 303A:8360 HID, so Codex can attach to the wrong
# instance and never receive reports from the current SWD control channel.
$legacyRootDevices = Get-PnpDevice -PresentOnly -Class HIDClass -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -like 'ROOT\HIDCLASS\*' } |
    Where-Object {
        $hardwareIds = Get-PnpDeviceProperty -InstanceId $_.InstanceId `
            -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue
        $hardwareIds.Data -contains 'root\CodexMicroHid'
    }
foreach ($legacyDevice in $legacyRootDevices) {
    if ([string]$legacyDevice.Problem -eq 'CM_PROB_DISABLED') {
        continue
    }
    & pnputil.exe /disable-device $legacyDevice.InstanceId /force
    if ($LASTEXITCODE -eq 3010) {
        Write-Warning "Legacy ROOT device will be disabled after the next Windows restart."
    } elseif ($LASTEXITCODE -ne 0) {
        throw "Legacy ROOT device disable failed with exit code $LASTEXITCODE"
    }
}

if ($codexDeviceIsPresent) {
    & pnputil.exe /disable-device $codexInstanceId /force
    if ($LASTEXITCODE -eq 3010) {
        $deviceNeedsReboot = $true
    } elseif ($LASTEXITCODE -ne 0) {
        throw "Device disable failed with exit code $LASTEXITCODE"
    }
}

& pnputil.exe /add-driver $inf /install
if ($LASTEXITCODE -eq 3010) {
    $deviceNeedsReboot = $true
} elseif ($LASTEXITCODE -ne 0) {
    throw "PnPUtil failed with exit code $LASTEXITCODE"
}

if (-not $codexDeviceIsPresent) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $swDeviceScript
    if ($LASTEXITCODE -ne 0) {
        throw "Software-device creation failed with exit code $LASTEXITCODE"
    }
}

if (-not $deviceNeedsReboot) {
    $currentCodexDevice = Get-PnpDevice -InstanceId $codexInstanceId -ErrorAction SilentlyContinue
    if (-not $currentCodexDevice -or [string]$currentCodexDevice.Problem -ne 'CM_PROB_NONE') {
        & pnputil.exe /enable-device $codexInstanceId
        if ($LASTEXITCODE -ne 0) {
            throw "Device enable failed with exit code $LASTEXITCODE"
        }
    }
} else {
    Write-Warning 'Windows must be restarted once to activate the updated driver.'
}

Write-Host 'Codex Micro SpaceMouse UMDF/SWD driver installed.'
Write-Host 'Verify with: .\.venv\Scripts\python.exe -m spacemouse_input codex-list'
Stop-Transcript | Out-Null
