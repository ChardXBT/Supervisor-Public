$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $projectRoot "assets\monitor-only.png"
$title = "Self-Recovering Automation - Monitor Only"
$pythonCandidates = @(
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
    (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
if (-not $pythonCandidates) {
    throw "Python 3.11 or newer was not found."
}
$python = $pythonCandidates[0]
$escapedRoot = $projectRoot.Replace("'", "''")
$escapedPython = $python.Replace("'", "''")
$command = "`$Host.UI.RawUI.WindowTitle='$title'; Set-Location -LiteralPath '$escapedRoot'; & '$escapedPython' monitor.py"

$window = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like "*$title*" } |
    Select-Object -First 1
if (-not $window) {
    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoLogo", "-NoProfile", "-NoExit", "-Command", $command) `
        -WindowStyle Normal | Out-Null
    Start-Sleep -Seconds 3
    $window = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like "*$title*" } |
        Select-Object -First 1
}
if (-not $window) {
    throw "The sanitized monitor window was not found."
}

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WindowCaptureBounds {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);
}
"@

$rect = New-Object WindowCaptureBounds+RECT
if (-not [WindowCaptureBounds]::GetWindowRect($window.MainWindowHandle, [ref]$rect)) {
    throw "Could not read the monitor window bounds."
}
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
    $null = [WindowCaptureBounds]::PostMessage(
        $window.MainWindowHandle,
        0x0010,
        [IntPtr]::Zero,
        [IntPtr]::Zero
    )
}

Write-Host "Captured sanitized monitor window to assets\monitor-only.png"
