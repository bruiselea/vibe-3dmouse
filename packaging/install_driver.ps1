[CmdletBinding()]
param(
    [string]$DriverDirectory = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$driverDirectory = [IO.Path]::GetFullPath($DriverDirectory)
$inf = Join-Path $driverDirectory 'VhidminiUm.inf'
$certificate = Join-Path $driverDirectory 'CodexMicroHid.cer'
$creator = Join-Path $driverDirectory 'swdevice_creator.exe'
$metadataPath = Join-Path $driverDirectory 'installed-driver.json'
$controlDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$controlFile = Join-Path $controlDirectory 'control.bin'
$instanceId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX'
$logDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'install.log'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
try {
    foreach ($path in @($inf, $certificate, $creator)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required driver file was not found: $path"
        }
    }

    $rootCertificate = Import-Certificate -FilePath $certificate -CertStoreLocation 'Cert:\LocalMachine\Root'
    Import-Certificate -FilePath $certificate -CertStoreLocation 'Cert:\LocalMachine\TrustedPublisher' | Out-Null

    New-Item -ItemType Directory -Path $controlDirectory -Force | Out-Null
    if (-not (Test-Path -LiteralPath $controlFile)) {
        [IO.File]::WriteAllBytes($controlFile, [byte[]]::new(68))
    } else {
        $stream = [IO.File]::Open($controlFile, 'Open', 'ReadWrite', 'ReadWrite')
        try {
            if ($stream.Length -lt 68) { $stream.SetLength(68) }
        } finally {
            $stream.Dispose()
        }
    }
    & icacls.exe $controlDirectory /grant '*S-1-5-32-545:(OI)(CI)M' /T /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to grant control-channel access: $LASTEXITCODE" }

    $presentDevice = Get-PnpDevice -InstanceId $instanceId -ErrorAction SilentlyContinue
    $isPresent = $false
    if ($presentDevice) {
        $property = Get-PnpDeviceProperty -InstanceId $instanceId `
            -KeyName 'DEVPKEY_Device_IsPresent' -ErrorAction SilentlyContinue
        $isPresent = $property.Data -eq $true
    }
    if ($isPresent) {
        & pnputil.exe /disable-device $instanceId /force | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) { throw "Device disable failed: $LASTEXITCODE" }
    }

    $driverOutput = & pnputil.exe /add-driver $inf /install 2>&1
    $driverExit = $LASTEXITCODE
    $driverOutput | Write-Host
    if ($driverExit -notin @(0, 3010)) { throw "PnPUtil driver install failed: $driverExit" }

    if (-not $isPresent) {
        & $creator
        if ($LASTEXITCODE -ne 0) { throw "Software device creation failed: $LASTEXITCODE" }
    }

    $device = Get-PnpDevice -InstanceId $instanceId -ErrorAction SilentlyContinue
    if (-not $device -or [string]$device.Problem -ne 'CM_PROB_NONE') {
        & pnputil.exe /enable-device $instanceId | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) { throw "Device enable failed: $LASTEXITCODE" }
    }

    $infProperty = Get-PnpDeviceProperty -InstanceId $instanceId `
        -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue
    $publishedName = [string]$infProperty.Data
    if (-not $publishedName) {
        $matches = [regex]::Matches(($driverOutput -join "`n"), 'oem\d+\.inf', 'IgnoreCase')
        if ($matches.Count -gt 0) { $publishedName = $matches[$matches.Count - 1].Value }
    }
    if (-not $publishedName -or $publishedName -notmatch '^oem\d+\.inf$') {
        throw 'Could not determine the installed driver package name.'
    }

    [ordered]@{
        product_version = '0.1.0-beta.1'
        instance_id = $instanceId
        published_name = $publishedName
        certificate_thumbprint = $rootCertificate.Thumbprint
    } | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

    Write-Host "Driver installed: $publishedName"
    if ($driverExit -eq 3010) { Write-Warning 'Windows must be restarted to finish driver installation.' }
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}

