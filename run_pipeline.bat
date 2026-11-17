@echo off
setlocal
if "%FXJEFE_PROJECT_DIR%"=="" set "FXJEFE_PROJECT_DIR=%USERPROFILE%\Documents\FXJEFE_Project"
if not exist "%FXJEFE_PROJECT_DIR%\" (
    echo PROJECT_ROOT does not exist: %FXJEFE_PROJECT_DIR%
    echo Clone this repo there, or set FXJEFE_PROJECT_DIR, then run setup_windows.bat.
    exit /b 1
)
if not exist "%FXJEFE_PROJECT_DIR%\fxjefe\Scripts\python.exe" (
    echo Virtualenv missing at %FXJEFE_PROJECT_DIR%\fxjefe
    echo Run setup_windows.bat first.
    exit /b 1
)
cd /d "%FXJEFE_PROJECT_DIR%"
REM Paper mode is the default. Pass --live only after the FTMO gate may send a real order.
"%FXJEFE_PROJECT_DIR%\fxjefe\Scripts\python.exe" "%FXJEFE_PROJECT_DIR%\run_pipeline.py" --project-dir "%FXJEFE_PROJECT_DIR%" %*
exit /b %ERRORLEVEL%
