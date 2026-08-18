[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$project = Join-Path $workspace 'native\vhidmini2\driver\umdf2\VhidminiUm.vcxproj'
$vsRoot = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools'
$msbuild = Join-Path $vsRoot 'MSBuild\Current\Bin\amd64\MSBuild.exe'
$vcTargets = Join-Path $vsRoot 'MSBuild\Microsoft\VC\v170'
$buildToolsUrl = 'https://download.visualstudio.microsoft.com/download/pr/fa1259b6-3659-4a26-a8b4-c42d40b343ab/c53677dd5d56679c4298323fd12a1ec504cc05e9e346c0866b178955a9dcbf4b/payload.vsix'
$buildToolsSha256 = 'C53677DD5D56679C4298323FD12A1EC504CC05E9E346C0866B178955A9DCBF4B'
$cache = Join-Path $env:LOCALAPPDATA 'SpaceMouseCodex\wdk-build-tools'
$vsix = Join-Path $cache 'wdk-build-tools.vsix'
$zip = Join-Path $cache 'wdk-build-tools.zip'
$expanded = Join-Path $cache 'expanded'
$overlay = Join-Path $cache 'vctargets'

if (-not (Test-Path -LiteralPath $msbuild)) {
    throw "Visual Studio 2022 Build Tools was not found: $msbuild"
}

New-Item -ItemType Directory -Path $cache -Force | Out-Null
if (-not (Test-Path -LiteralPath $vsix) -or
    (Get-FileHash -LiteralPath $vsix -Algorithm SHA256).Hash -ne $buildToolsSha256) {
    Invoke-WebRequest -Uri $buildToolsUrl -OutFile $vsix
}
if ((Get-FileHash -LiteralPath $vsix -Algorithm SHA256).Hash -ne $buildToolsSha256) {
    throw 'The downloaded Microsoft WDK Build Tools VSIX failed SHA-256 verification.'
}

if (-not (Test-Path -LiteralPath $expanded)) {
    Copy-Item -LiteralPath $vsix -Destination $zip -Force
    Expand-Archive -LiteralPath $zip -DestinationPath $expanded -Force
}
if (-not (Test-Path -LiteralPath $overlay)) {
    Copy-Item -LiteralPath $vcTargets -Destination $overlay -Recurse
}

$wdkTargets = Join-Path $expanded 'Contents\MSBuild\Microsoft\VC\v170\*'
Copy-Item -Path $wdkTargets -Destination $overlay -Recurse -Force
$overlayProperty = $overlay + '\'

& $msbuild $project /t:Rebuild /p:Configuration=$Configuration /p:Platform=x64 `
    /p:Driver_SpectreMitigation=false /p:SpectreMitigation=false `
    /p:Inf2CatUseLocalTime=true `
    "/p:VCTargetsPath=$overlayProperty" /m /v:minimal
if ($LASTEXITCODE -ne 0) {
    throw "Driver build failed with exit code $LASTEXITCODE"
}

$package = Join-Path (Split-Path -Parent $project) "x64\$Configuration\VhidminiUm"
Write-Host "Driver package: $package"
