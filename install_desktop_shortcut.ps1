# Creates a desktop shortcut (Windows) for the ESP-Claw Serial Control GUI.
$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "ESP-Claw Serial Control"

$PythonCmd = Get-Command pythonw -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Error "Python not found on PATH. Install Python from python.org (check 'Add python.exe to PATH' during setup), then run this script again."
    exit 1
}
$PythonBin = $PythonCmd.Source

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "$AppName.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonBin
$Shortcut.Arguments = "-m espclaw_ctl.gui"
$Shortcut.WorkingDirectory = $RepoDir
$Shortcut.Description = "Control ESP-Claw (ESP32-S3) over USB serial"
$Shortcut.WindowStyle = 1
$Shortcut.Save()

Write-Host "Shortcut created at: $ShortcutPath"
Write-Host "Make sure dependencies are installed: pip install -r requirements.txt (or pip install -e .)"
