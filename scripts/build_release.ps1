[CmdletBinding()]
param(
    [switch]$SkipDriver,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$spec = Join-Path $workspace 'packaging\SpaceMouseCodexBridge.spec'
$dist = Join-Path $workspace 'dist'
$work = Join-Path $workspace 'build\pyinstaller'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment was not found: $python"
}

Push-Location $workspace
try {
    & $python -m pip install -r (Join-Path $workspace 'requirements-release.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Release dependencies failed to install.' }

    & $python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }

    & $python (Join-Path $workspace 'scripts\create_release_icon.py')
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }

    if (-not $SkipDriver) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
            (Join-Path $workspace 'scripts\build_driver.ps1') -Configuration Release
        if ($LASTEXITCODE -ne 0) { throw 'Release driver build failed.' }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
            (Join-Path $workspace 'scripts\build_swdevice_helper.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Software-device helper build failed.' }
    }

    & $python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work $spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    if (-not $SkipInstaller) {
        $isccCandidates = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        )
        $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
            Select-Object -First 1
        if (-not $iscc) {
            throw 'Inno Setup 6 was not found. Install with: winget install --id JRSoftware.InnoSetup --exact'
        }
        & $iscc (Join-Path $workspace 'packaging\SpaceMouseCodexBridge.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

        $installer = Join-Path $dist 'installer\SpaceMouseCodexBridge-0.1.0-beta.1-x64-setup.exe'
        $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([IO.Path]::GetFileName($installer))" | Set-Content `
            -LiteralPath ($installer + '.sha256') -Encoding ascii
        Copy-Item -LiteralPath (Join-Path $workspace 'BETA_README.md') `
            -Destination (Join-Path (Split-Path -Parent $installer) 'README.md') -Force
        Copy-Item -LiteralPath (Join-Path $workspace 'THIRD_PARTY_NOTICES.txt') `
            -Destination (Split-Path -Parent $installer) -Force
        Write-Host "Installer: $installer"
        Write-Host "SHA-256: $hash"
    }
} finally {
    Pop-Location
}
