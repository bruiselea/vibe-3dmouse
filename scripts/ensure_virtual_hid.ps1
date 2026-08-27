[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CreatorPath
)

$ErrorActionPreference = 'Stop'
$creator = [IO.Path]::GetFullPath($CreatorPath)
$logDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'hid-recovery.log'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-RecoveryLog([string]$Message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss.fff} {1}' -f [DateTime]::Now, $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding utf8
}

function Get-CodexHid {
    Get-PnpDevice -PresentOnly -Class HIDClass -ErrorAction SilentlyContinue | Where-Object {
        $_.InstanceId -like 'HID\VID_303A&PID_8360*' -and
        [string]$_.Problem -eq 'CM_PROB_NONE'
    } | Select-Object -First 1
}

function Remove-StaleOwnedDevices {
    $stableId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX_RUNTIME'
    $staleDevices = Get-PnpDevice -PresentOnly:$false -ErrorAction SilentlyContinue | Where-Object {
        $_.InstanceId -like 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX*' -and
        $_.InstanceId -ne $stableId -and
        (Get-PnpDeviceProperty -InstanceId $_.InstanceId `
            -KeyName 'DEVPKEY_Device_IsPresent' -ErrorAction SilentlyContinue).Data -ne $true
    }
    foreach ($device in $staleDevices) {
        Write-RecoveryLog "Removing stale owned SWD: $($device.InstanceId)"
        & pnputil.exe /remove-device ([string]$device.InstanceId) /force | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) {
            Write-RecoveryLog "WARNING: stale SWD removal failed ($LASTEXITCODE): $($device.InstanceId)"
        }
    }
}

try {
    if (-not (Test-Path -LiteralPath $creator -PathType Leaf)) {
        throw "Software-device creator was not found: $creator"
    }
    Remove-StaleOwnedDevices
    if (Get-CodexHid) {
        Write-RecoveryLog 'Virtual HID is already present.'
        exit 0
    }

    $stableId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX_RUNTIME'
    $stableDevice = Get-PnpDevice -InstanceId $stableId -ErrorAction SilentlyContinue
    if ($stableDevice) {
        Write-RecoveryLog "Removing stale stable SWD: $stableId"
        & pnputil.exe /remove-device $stableId /force | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) {
            throw "Stale SWD removal failed: $LASTEXITCODE"
        }
    }

    Write-RecoveryLog 'Creating stable virtual HID.'
    $creatorOutput = & $creator --stable 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Software-device creation failed ($LASTEXITCODE): $($creatorOutput -join ' ')"
    }
    Write-RecoveryLog ($creatorOutput -join ' ')

    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        if (Get-CodexHid) {
            Write-RecoveryLog 'Virtual HID recovery completed.'
            exit 0
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Virtual HID did not appear within 20 seconds.'
} catch {
    Write-RecoveryLog "ERROR: $($_.Exception.Message)"
    exit 1
}
