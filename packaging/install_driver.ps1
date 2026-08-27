[CmdletBinding()]
param(
    [string]$DriverDirectory = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'
$driverDirectory = [IO.Path]::GetFullPath($DriverDirectory)
$inf = Join-Path $driverDirectory 'VhidminiUm.inf'
$certificate = Join-Path $driverDirectory 'CodexMicroHid.cer'
$creator = Join-Path $driverDirectory 'swdevice_creator.exe'
$ensureScript = Join-Path $driverDirectory 'ensure_virtual_hid.ps1'
$metadataPath = Join-Path $driverDirectory 'installed-driver.json'
$controlDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$controlFile = Join-Path $controlDirectory 'control.bin'
$instanceId = $null
$logDirectory = Join-Path $env:ProgramData 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'install.log'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
try {
    foreach ($path in @($inf, $certificate, $creator, $ensureScript)) {
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

    $presentDevice = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
        ($_.InstanceId -like 'SWD\VID_303A&PID_8360\SPACEMOUSE_CODEX*' -or
            $_.InstanceId -like 'SWD\*\VID_303A&PID_8360&SPACEMOUSE_CODEX*') -and
        $_.FriendlyName -eq 'Codex Micro SpaceMouse Bridge'
    } | Select-Object -First 1
    if ($presentDevice) { $instanceId = [string]$presentDevice.InstanceId }
    $isPresent = $false
    if ($presentDevice) {
        $property = Get-PnpDeviceProperty -InstanceId $presentDevice.InstanceId `
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
        $creatorOutput = & $creator
        $creatorOutput | Write-Host
        if ($LASTEXITCODE -ne 0) { throw "Software device creation failed: $LASTEXITCODE" }
        $reportedId = @($creatorOutput) | Where-Object { $_ -match '^SWD\\' } |
            Select-Object -Last 1
        if (-not $reportedId) { throw 'Software device creator did not report an instance ID.' }
        $instanceId = [string]$reportedId
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
        product_version = '0.1.0-beta.3'
        instance_id = $instanceId
        published_name = $publishedName
        certificate_thumbprint = $rootCertificate.Thumbprint
    } | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

    Write-Host "Driver installed: $publishedName"
    $taskName = 'VibeSpaceMouseBridge-EnsureVirtualHid'
    $systemTaskName = "$taskName-System"
    $powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $taskArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -CreatorPath "{1}"' -f `
        $ensureScript, $creator
    $taskAction = New-ScheduledTaskAction -Execute $powerShell -Argument $taskArguments
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $startupTrigger.Delay = 'PT20S'
    $installIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $installIdentity.Name
    $systemPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $userPrincipal = New-ScheduledTaskPrincipal -UserId $installIdentity.Name -LogonType Interactive -RunLevel Highest
    $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $systemTaskName -Action $taskAction `
        -Trigger $startupTrigger -Principal $systemPrincipal `
        -Settings $taskSettings -Force | Out-Null
    Register-ScheduledTask -TaskName $taskName -Action $taskAction `
        -Trigger $logonTrigger -Principal $userPrincipal `
        -Settings $taskSettings -Force | Out-Null
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $registeredTask = $scheduler.GetFolder('\').GetTask($taskName)
    $installUserSid = $installIdentity.User.Value
    $registeredTask.SetSecurityDescriptor(
        "D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;$installUserSid)",
        0
    )
    if ($driverExit -eq 3010) { Write-Warning 'Windows must be restarted to finish driver installation.' }
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}
