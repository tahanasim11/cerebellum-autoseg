@echo off
setlocal EnableExtensions
title Cerebellum AutoSeg - compare with manual segmentation
set "CSEG_HOME=%LOCALAPPDATA%\CerebSeg"
set "PY=%CSEG_HOME%\env\Scripts\python.exe"
if not exist "%PY%" goto nosetup

"%PY%" "%~dp0tools\compare_masks.py"
echo.
pause
exit /b 0

:nosetup
echo.
echo Setup has not been run yet. Double-click "1_SETUP (run once).bat" first.
echo.
pause
exit /b 1
