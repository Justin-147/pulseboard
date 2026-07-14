param(
    [switch]$Install,
    [switch]$Uninstall,
    [string]$StartupPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$startup = if ($StartupPath) { $StartupPath } else { [Environment]::GetFolderPath("Startup") }
if (-not (Test-Path $startup)) { New-Item -ItemType Directory -Path $startup -Force | Out-Null }
$shortcutPath = Join-Path $startup "PulseBoard.lnk"

if ($Install) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'start.ps1')`""
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = "PulseBoard local system resource dashboard"
    $shortcut.Save()
    Write-Host "Autostart enabled. PulseBoard will open after Windows login."
    exit 0
}

if ($Uninstall) {
    if (Test-Path $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force }
    Write-Host "Autostart disabled."
    exit 0
}

throw "Use -Install or -Uninstall."
