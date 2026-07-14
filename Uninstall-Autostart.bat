@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\autostart.ps1" -Uninstall
if errorlevel 1 pause

