@echo off
REM Quick launcher - assumes SNES9x is in PATH or common location

set "ROM=%~dp0build\SuperDragonsLairArcade.sfc"

REM Try common SNES9x locations
if exist "C:\Program Files\snes9x\snes9x-x64.exe" (
    start "" "C:\Program Files\snes9x\snes9x-x64.exe" "%ROM%"
    exit /b 0
)

if exist "C:\Program Files (x86)\snes9x\snes9x.exe" (
    start "" "C:\Program Files (x86)\snes9x\snes9x.exe" "%ROM%"
    exit /b 0
)

REM Try PATH
where snes9x-x64.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" snes9x-x64.exe "%ROM%"
    exit /b 0
)

where snes9x.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" snes9x.exe "%ROM%"
    exit /b 0
)

REM Not found
echo SNES9x not found!
echo.
echo Please either:
echo 1. Install SNES9x to C:\Program Files\snes9x\
echo 2. Add SNES9x to your PATH
echo 3. Edit play.bat to set the correct path
echo.
echo Download SNES9x from: https://www.snes9x.com/downloads.php
pause
