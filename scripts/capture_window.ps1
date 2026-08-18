[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ProcessName,
    [Parameter(Mandatory)]
    [string]$WindowTitlePattern,
    [Parameter(Mandatory)]
    [string]$OutputPath,
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class WindowCaptureNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("dwmapi.dll")]
    public static extern int DwmGetWindowAttribute(
        IntPtr hwnd,
        int dwAttribute,
        out RECT pvAttribute,
        int cbAttribute
    );
}
'@

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
do {
    $process = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like $WindowTitlePattern } |
        Select-Object -First 1
    if ($process) { break }
    Start-Sleep -Milliseconds 200
} while ([DateTime]::UtcNow -lt $deadline)

if (-not $process) {
    throw "Window was not found: $ProcessName / $WindowTitlePattern"
}

[WindowCaptureNative]::ShowWindow($process.MainWindowHandle, 9) | Out-Null
[WindowCaptureNative]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 500

$bounds = [WindowCaptureNative+RECT]::new()
$result = [WindowCaptureNative]::DwmGetWindowAttribute(
    $process.MainWindowHandle,
    9,
    [ref]$bounds,
    [Runtime.InteropServices.Marshal]::SizeOf($bounds)
)
if ($result -ne 0) { throw "DwmGetWindowAttribute failed: $result" }

$width = $bounds.Right - $bounds.Left
$height = $bounds.Bottom - $bounds.Top
if ($width -le 0 -or $height -le 0) { throw 'Window bounds are invalid.' }

$absoluteOutput = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($absoluteOutput)) | Out-Null
$bitmap = [Drawing.Bitmap]::new($width, $height)
$graphics = [Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($absoluteOutput, [Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

Write-Output $absoluteOutput
