@echo off
setlocal EnableExtensions
title Cerebellum AutoSeg - segment scans
set "CSEG_HOME=%LOCALAPPDATA%\CerebSeg"
set "PY=%CSEG_HOME%\env\Scripts\python.exe"
if not exist "%PY%" goto nosetup

rem Double-click to choose scans in a window, or drag .nii.gz files onto this file.
"%PY%" "%~dp0tools\cerebellum_autoseg.py" %*
echo.
pause
exit /b 0

:nosetup
echo.
echo Setup has not been run yet. Double-click "1_SETUP (run once).bat" first.
echo.
pause
exit /b 1
