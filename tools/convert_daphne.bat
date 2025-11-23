@echo off
REM Batch wrapper for converting Daphne CDROM contents to MP4
REM This script automates the conversion process with sensible defaults

setlocal

REM Set paths
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "DAPHNE_DIR=e:\gh\DaphneCDROM"
set "FRAMEFILE=%DAPHNE_DIR%\framefile\dlcdrom.TXT"
set "OUTPUT=%PROJECT_ROOT%\data\videos\dl_arcade.mp4"
set "LOGFILE=%SCRIPT_DIR%convert_daphne.log"

echo ========================================
echo Daphne CDROM to MP4 Conversion
echo ========================================
echo.

REM Check if DaphneCDROM directory exists
if not exist "%DAPHNE_DIR%" (
    echo ERROR: DaphneCDROM directory not found at: %DAPHNE_DIR%
    echo Please ensure the Daphne CDROM files are available.
    echo.
    pause
    exit /b 1
)

REM Check if framefile exists
if not exist "%FRAMEFILE%" (
    echo ERROR: Framefile not found at: %FRAMEFILE%
    echo.
    pause
    exit /b 1
)

echo Source: %FRAMEFILE%
echo Output: %OUTPUT%
echo Log:    %LOGFILE%
echo.
echo Starting conversion...
echo This may take several minutes. Progress will be logged to: %LOGFILE%
echo.

REM Run the Python script with quiet mode
python "%SCRIPT_DIR%convert_daphne.py" --framefile "%FRAMEFILE%" --output "%OUTPUT%" --quiet --logfile "%LOGFILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Conversion completed successfully!
    echo ========================================
    echo Output file: %OUTPUT%
    echo.
) else (
    echo.
    echo ========================================
    echo Conversion failed with error code: %ERRORLEVEL%
    echo ========================================
    echo Check the log file for details: %LOGFILE%
    echo.
    pause
    exit /b %ERRORLEVEL%
)

endlocal
