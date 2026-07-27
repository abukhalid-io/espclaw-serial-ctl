@echo off
REM Creates a desktop shortcut (Windows) for the ESP-Claw Serial Control GUI.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_desktop_shortcut.ps1"
pause
