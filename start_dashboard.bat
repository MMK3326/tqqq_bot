@echo off
setlocal

cd /d "%~dp0"

wscript.exe //B "%~dp0.launcher\start_dashboard_hidden.vbs"
exit /b 0
