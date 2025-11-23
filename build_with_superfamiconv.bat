@echo off
REM Build script that uses superfamiconv instead of gracon.py
REM This is significantly faster (~100x) for graphics conversion

echo Building SNES Super Dragon's Lair Arcade with superfamiconv...
echo.

REM Set environment variable to tell Makefile to use superfamiconv
set USE_SUPERFAMICONV=1

REM Run make in WSL
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && export USE_SUPERFAMICONV=1 && make"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build completed successfully!
    echo ========================================
    echo.
    wsl bash -c "ls -lh /mnt/e/gh/SNES-SuperDragonsLairArcade/build/*.sfc"
) else (
    echo.
    echo ========================================
    echo Build failed with error code %ERRORLEVEL%
    echo ========================================
)

pause
