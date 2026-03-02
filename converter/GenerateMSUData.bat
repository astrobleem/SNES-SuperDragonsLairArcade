@echo off
cd /d "%~dp0"
where uv >nul 2>&1 || pip install uv
uv run --with Pillow --with numpy gui.py %*
if errorlevel 1 pause
