@echo off
REM Test extraction of a single Dragon's Lair chapter to verify timing alignment
REM This extracts video frames and audio for one chapter to verify the conversion worked

setlocal

set "CHAPTER_XML=data\events\introduction_castle_exterior.xml"
set "CHAPTER_NAME=introduction_castle_exterior"
set "VIDEO_FILE=data\videos\dl_arcade.mp4"
set "OUTPUT_DIR=data\chapters\%CHAPTER_NAME%_test"

echo =========================================
echo Single Chapter Extraction Test
echo =========================================
echo.
echo Chapter: %CHAPTER_NAME%
echo Video: %VIDEO_FILE%
echo Output: %OUTPUT_DIR%
echo.

REM Check if video file exists
if not exist "%VIDEO_FILE%" (
    echo ERROR: Video file not found: %VIDEO_FILE%
    echo Make sure the FPS conversion completed successfully.
    pause
    exit /b 1
)

REM Check if XML exists
if not exist "%CHAPTER_XML%" (
    echo ERROR: Chapter XML not found: %CHAPTER_XML%
    pause
    exit /b 1
)

REM Check video frame rate
echo Checking video frame rate...
for /f "delims=" %%i in ('wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 data/videos/dl_arcade.mp4"') do set FPS=%%i
echo Video FPS: %FPS%

if not "%FPS%"=="24000/1001" (
    echo WARNING: Video is not 23.976 fps! Expected 24000/1001, got %FPS%
    echo The timing may not align correctly.
    set /p "CONTINUE=Continue anyway? (y/n): "
    if /i not "%CONTINUE%"=="y" (
        exit /b 0
    )
)

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo.
echo Extracting chapter with xmlsceneparser.py...
echo This will take about 30-60 seconds...
echo.

REM Run the XML scene parser with video extraction
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/xmlsceneparser.py -infile %CHAPTER_XML% -outfolder %OUTPUT_DIR% -videofile %VIDEO_FILE%"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Extraction failed!
    pause
    exit /b 1
)

echo.
echo =========================================
echo Extraction Complete!
echo =========================================
echo.

REM Count extracted files
for /f %%i in ('dir /b "%OUTPUT_DIR%\video_*.png" 2^>nul ^| find /c /v ""') do set VIDEO_FRAMES=%%i
for /f %%i in ('dir /b "%OUTPUT_DIR%\audio.*.wav" 2^>nul ^| find /c /v ""') do set AUDIO_FILES=%%i

echo Results:
echo   Video frames: %VIDEO_FRAMES% PNG files
echo   Audio files: %AUDIO_FILES% WAV files
echo   Location: %OUTPUT_DIR%
echo.

if "%VIDEO_FRAMES%"=="0" (
    echo WARNING: No video frames extracted!
    echo Check the chapter XML timestamps and video content.
) else (
    echo SUCCESS: Video frames extracted successfully!
    echo.
    echo To verify timing alignment:
    echo 1. Check the first frame: %OUTPUT_DIR%\video_000001.gfx_video.png
    echo 2. Play the audio: %OUTPUT_DIR%\audio.sfx_video.wav
    echo 3. Compare with video at timestamp 0:53 ^(start of chapter^)
)

echo.
echo If timing looks correct, you can:
echo 1. Uncomment line 413 in makefile
echo 2. Run 'make' to extract all 516 chapters

echo.
pause
endlocal
