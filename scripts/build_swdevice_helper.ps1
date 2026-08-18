[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$source = Join-Path $workspace 'native\swdevice_creator\main.cpp'
$output = Join-Path $workspace 'native\swdevice_creator\x64\Release'
$vsDevCmd = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'

New-Item -ItemType Directory -Path $output -Force | Out-Null
$command = '"{0}" -arch=x64 -host_arch=x64 && cl.exe /nologo /EHsc /O2 /DUNICODE /D_UNICODE "{1}" /Fe:"{2}\swdevice_creator.exe" /link Swdevice.lib' -f $vsDevCmd, $source, $output
& cmd.exe /d /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw "Software-device helper build failed with exit code $LASTEXITCODE"
}
