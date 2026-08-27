[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'VibeSpaceMouseBridge-EnsureVirtualHid'
$systemTaskName = "$taskName-System"
$workspace = Split-Path -Parent $PSScriptRoot
$ensureScript = Join-Path $workspace 'scripts\ensure_virtual_hid.ps1'
$creator = Join-Path $workspace 'native\swdevice_creator\x64\Release\swdevice_creator.exe'
$logDirectory = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex'
$logPath = Join-Path $logDirectory 'install_hid_recovery_task.log'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)

if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
        -Verb RunAs -PassThru -Wait
    if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath }
    exit $(if ($null -eq $process.ExitCode) { 1 } else { $process.ExitCode })
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force | Out-Null
trap {
    Write-Error ($_ | Out-String)
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

foreach ($path in @($ensureScript, $creator)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required recovery file was not found: $path"
    }
}

$powerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -CreatorPath "{1}"' -f `
    $ensureScript, $creator
$action = New-ScheduledTaskAction -Execute $powerShell -Argument $arguments
$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$startupTrigger.Delay = 'PT20S'
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$systemPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$userPrincipal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $systemTaskName -Action $action `
    -Trigger $startupTrigger -Principal $systemPrincipal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName $taskName -Action $action `
    -Trigger $logonTrigger -Principal $userPrincipal -Settings $settings -Force | Out-Null
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$registeredTask = $scheduler.GetFolder('\').GetTask($taskName)
$userSid = $identity.User.Value
$registeredTask.SetSecurityDescriptor(
    "D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;$userSid)",
    0
)
Start-ScheduledTask -TaskName $taskName
Write-Host "Registered: $systemTaskName"
Write-Host "Registered and started: $taskName"
Stop-Transcript | Out-Null
