@echo off
REM Launch SNES9x with Super Dragon's Lair Arcade ROM

set "ROM_PATH=%~dp0build\SuperDragonsLairArcade.sfc"
set "SNES9X_PATH=C:\Program Files\snes9x\snes9x-x64.exe"

REM Check if ROM exists
if not exist "%ROM_PATH%" (
    echo ERROR: ROM not found at %ROM_PATH%
    echo.
    echo Please build the ROM first with:
    echo   build_with_superfamiconv.bat
    echo.
    pause
    exit /b 1
)

REM Check if SNES9x exists at default location
if not exist "%SNES9X_PATH%" (
    echo SNES9x not found at default location: %SNES9X_PATH%
    echo.
    echo Please install SNES9x or update SNES9X_PATH in this script.
    echo Download from: https://www.snes9x.com/downloads.php
    echo.
    pause
    exit /b 1
)

echo Starting SNES9x with Super Dragon's Lair Arcade...
echo ROM: %ROM_PATH%
echo.

start "" "%SNES9X_PATH%" "%ROM_PATH%"

echo SNES9x launched!
