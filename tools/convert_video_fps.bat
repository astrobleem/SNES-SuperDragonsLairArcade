@echo off
REM Convert Dragon's Lair video from 29.97 fps (Daphne) to 23.976 fps (DirkSimple XML)
REM This ensures video timing aligns with the XML chapter event timings

setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "INPUT=%PROJECT_ROOT%\data\videos\dl_arcade.mp4"
set "OUTPUT=%PROJECT_ROOT%\data\videos\dl_arcade_23976.mp4"
set "BACKUP=%PROJECT_ROOT%\data\videos\dl_arcade_29.97fps_backup.mp4"

echo =========================================
echo Dragon's Lair Video FPS Conversion
echo =========================================
echo.
echo Converting from 29.97 fps to 23.976 fps
echo This will take approximately 15-30 minutes...
echo.

REM Check if input file exists
if not exist "%INPUT%" (
    echo ERROR: Input file not found: %INPUT%
    pause
    exit /b 1
)

REM Check if output already exists
if exist "%OUTPUT%" (
    echo WARNING: Output file already exists: %OUTPUT%
    set /p "OVERWRITE=Overwrite? (y/n): "
    if /i not "%OVERWRITE%"=="y" (
        echo Conversion cancelled.
        pause
        exit /b 0
    )
    del "%OUTPUT%"
)

echo Step 1/3: Converting video...
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && ffmpeg -i data/videos/dl_arcade.mp4 -r 24000/1001 -c:v libx264 -preset slow -crf 18 -c:a copy data/videos/dl_arcade_23976.mp4"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Conversion failed!
    pause
    exit /b 1
)

echo.
echo Step 2/3: Verifying output...
for /f "delims=" %%i in ('wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 data/videos/dl_arcade_23976.mp4"') do set NEW_FPS=%%i
echo New frame rate: %NEW_FPS%

if not "%NEW_FPS%"=="24000/1001" (
    echo WARNING: Frame rate verification failed! Expected 24000/1001, got %NEW_FPS%
    echo The file was created but may not be correct.
    pause
    exit /b 1
)

echo.
echo Step 3/3: Backing up original and replacing...
set /p "REPLACE=Replace original file with converted version? (y/n): "
if /i "%REPLACE%"=="y" (
    move "%INPUT%" "%BACKUP%"
    move "%OUTPUT%" "%INPUT%"
    echo.
    echo =========================================
    echo Conversion Complete!
    echo =========================================
    echo Original backed up to: %BACKUP%
    echo New 23.976 fps video: %INPUT%
    echo.
    echo Next steps:
    echo 1. Uncomment line 413 in makefile to enable video extraction
    echo 2. Run 'make' to generate chapter video/audio assets
) else (
    echo.
    echo =========================================
    echo Conversion Complete!
    echo =========================================
    echo Original file unchanged: %INPUT%
    echo Converted file saved to: %OUTPUT%
    echo.
    echo To use the converted file:
    echo   move "%INPUT%" "%BACKUP%"
    echo   move "%OUTPUT%" "%INPUT%"
)

echo.
pause
endlocal
