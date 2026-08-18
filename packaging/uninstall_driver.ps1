[CmdletBinding()]
param(
    [string]$InstallDirectory
)

$ErrorActionPreference = 'Stop'
$installDirectory = [IO.Path]::GetFullPath($InstallDirectory)
$app = Join-Path $installDirectory 'SpaceMouseCodexBridge.exe'
$driverDirectory = Join-Path $installDirectory 'driver'
$metadataPath = Join-Path $driverDirectory 'installed-driver.json'
$defaultInstanceId = 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX'
$logDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'uninstall.log'
$controlFile = Join-Path $logDirectory 'control.bin'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
try {
    if (Test-Path -LiteralPath $app -PathType Leaf) {
        & $app --shutdown
        $deadline = [DateTime]::UtcNow.AddSeconds(25)
        do {
            $running = Get-Process -Name 'SpaceMouseCodexBridge' -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -eq $app }
            if (-not $running) { break }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)
        if ($running) { Write-Warning 'The application is still running; some files may require a restart.' }
    }

    $metadata = $null
    if (Test-Path -LiteralPath $metadataPath -PathType Leaf) {
        $metadata = Get-Content -Raw -LiteralPath $metadataPath | ConvertFrom-Json
    }
    $instanceId = if ($metadata.instance_id) { [string]$metadata.instance_id } else { $defaultInstanceId }
    $device = Get-PnpDevice -InstanceId $instanceId -ErrorAction SilentlyContinue
    if ($device) {
        & pnputil.exe /remove-device $instanceId /force | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) { Write-Warning "Device removal failed: $LASTEXITCODE" }
    }

    if ($metadata.published_name -and [string]$metadata.published_name -match '^oem\d+\.inf$') {
        & pnputil.exe /delete-driver ([string]$metadata.published_name) /uninstall /force | Out-Null
        if ($LASTEXITCODE -notin @(0, 3010)) { Write-Warning "Driver package removal failed: $LASTEXITCODE" }
    }

    # CSV keeps the provider value stable even when Windows displays PnPUtil in Japanese.
    $remaining = (& pnputil.exe /enum-drivers /class HIDClass /format csv 2>&1) -join "`n"
    if ($remaining -notmatch 'SpaceMouse Codex' -and $metadata.certificate_thumbprint) {
        $thumbprint = [string]$metadata.certificate_thumbprint
        foreach ($store in @('Cert:\LocalMachine\Root', 'Cert:\LocalMachine\TrustedPublisher')) {
            $certificate = Get-ChildItem -Path $store | Where-Object Thumbprint -eq $thumbprint
            if ($certificate) { $certificate | Remove-Item -Force }
        }
    }

    $service = @(
        (Join-Path $env:ProgramW6432 '3Dconnexion\3DxWare\3DxWinCore\3DxService.exe'),
        (Join-Path ${env:ProgramFiles(x86)} '3Dconnexion\3DxWare\3DxWinCore\3DxService.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
    if ($service -and -not (Get-Process -Name '3DxService' -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $service -WorkingDirectory (Split-Path -Parent $service) -WindowStyle Hidden
    }

    # These files are generated at install/runtime and are therefore not tracked by Inno Setup.
    Remove-Item -LiteralPath $metadataPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $controlFile -Force -ErrorAction SilentlyContinue
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}
