@echo off
cd /d "%~dp0"
python gui.py %*
if errorlevel 1 pause
