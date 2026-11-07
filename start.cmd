@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-stack.ps1" -Action Start -ShowLogs
if errorlevel 1 pause
