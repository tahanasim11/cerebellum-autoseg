@echo off
setlocal EnableExtensions
title Cerebellum AutoSeg - one-time setup
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem  Everything is installed into one private folder in your user profile.
rem  No administrator rights are needed and nothing else on the PC is changed.
rem  To uninstall later, just delete the folder shown below.
rem ---------------------------------------------------------------------------
set "CSEG_HOME=%LOCALAPPDATA%\CerebSeg"
set "UV=%CSEG_HOME%\bin\uv.exe"
set "PY=%CSEG_HOME%\env\Scripts\python.exe"
set "UV_NATIVE_TLS=1"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_PYTHON_INSTALL_DIR=%CSEG_HOME%\python"
set "UV_CACHE_DIR=%CSEG_HOME%\uvc"
set "UV_HTTP_TIMEOUT=300"
set "SYNTHSEG_COMMIT=2a2aa3bbfccb83f8253a51ca8b329b9938a2646d"
set "FS_ANNEX=https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/repo/annex.git/annex/objects"
set "ROBUST_KEY=SHA256E-s214606800--7bc30bf5c3d204f20c4a6cb5a283aedbcab6af1de927cda783f59b67d19cb01c.0.h5"

echo.
echo  ======================================================================
echo   Cerebellum AutoSeg: one-time setup
echo.
echo   Installs into: %CSEG_HOME%
echo   Needs: internet, about 3 GB of free disk space, 5 to 20 minutes.
echo   No administrator rights needed. Your scans are not touched.
echo  ======================================================================
echo.

where curl.exe >nul 2>nul
if errorlevel 1 goto fail_oldwindows
where tar.exe >nul 2>nul
if errorlevel 1 goto fail_oldwindows

if not exist "%CSEG_HOME%\bin" mkdir "%CSEG_HOME%\bin"

rem ---- 1. uv (a small, self-contained Python installer) ----------------------
echo [1/5] Getting the Python installer (uv)...
if exist "%UV%" goto have_uv
curl.exe -L --fail --retry 3 -o "%CSEG_HOME%\uv.zip" "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
if errorlevel 1 goto fail_net
tar.exe -xf "%CSEG_HOME%\uv.zip" -C "%CSEG_HOME%\bin"
if errorlevel 1 goto fail
del /q "%CSEG_HOME%\uv.zip"
:have_uv
if not exist "%UV%" goto fail
echo       done.

rem ---- 2. private Python 3.11 environment ------------------------------------
echo [2/5] Creating a private Python 3.11 environment...
if exist "%PY%" goto have_env
rem Always use 64-bit Intel/AMD (x64) Python: TensorFlow has no Windows ARM build,
rem and x64 Python also runs on ARM laptops through Windows emulation.
"%UV%" venv --python cpython-3.11-windows-x86_64-none "%CSEG_HOME%\env"
if errorlevel 1 goto fail_net
:have_env
echo       done.

rem ---- 3. libraries -----------------------------------------------------------
echo [3/5] Installing TensorFlow and imaging libraries. This is the longest step...
"%UV%" pip install --python "%PY%" "tensorflow==2.15.1" "numpy==1.23.5" "scipy==1.13.1" "nibabel==5.2.1" "psutil==7.0.0"
if errorlevel 1 goto fail_net
echo       done.

rem ---- 4. SynthSeg code (pinned version) -------------------------------------
echo [4/5] Downloading the SynthSeg code...
if exist "%CSEG_HOME%\SynthSeg\scripts\commands\SynthSeg_predict.py" goto have_code
curl.exe -L --fail --retry 3 -o "%CSEG_HOME%\synthseg.zip" "https://github.com/BBillot/SynthSeg/archive/%SYNTHSEG_COMMIT%.zip"
if errorlevel 1 goto fail_net
if exist "%CSEG_HOME%\SynthSeg-%SYNTHSEG_COMMIT%" rmdir /s /q "%CSEG_HOME%\SynthSeg-%SYNTHSEG_COMMIT%"
tar.exe -xf "%CSEG_HOME%\synthseg.zip" -C "%CSEG_HOME%"
if errorlevel 1 goto fail
if exist "%CSEG_HOME%\SynthSeg" rmdir /s /q "%CSEG_HOME%\SynthSeg"
move "%CSEG_HOME%\SynthSeg-%SYNTHSEG_COMMIT%" "%CSEG_HOME%\SynthSeg" >nul
if errorlevel 1 goto fail
del /q "%CSEG_HOME%\synthseg.zip"
:have_code
echo       done.

rem ---- 5. SynthSeg-robust 2.0 model weights (official FreeSurfer server) -----
echo [5/5] Downloading the SynthSeg-robust 2.0 model (about 215 MB)...
if exist "%CSEG_HOME%\SynthSeg\models\synthseg_robust_2.0.h5" goto have_model
curl.exe -L --fail --retry 3 -o "%CSEG_HOME%\SynthSeg\models\synthseg_robust_2.0.h5.part" "%FS_ANNEX%/187/db4/%ROBUST_KEY%/%ROBUST_KEY%"
if errorlevel 1 goto fail_net
move /y "%CSEG_HOME%\SynthSeg\models\synthseg_robust_2.0.h5.part" "%CSEG_HOME%\SynthSeg\models\synthseg_robust_2.0.h5" >nul
:have_model
echo       done.

echo.
echo Checking that everything works...
"%PY%" "%~dp0tools\verify_install.py"
if errorlevel 1 goto fail_verify

rem free about 1 GB of temporary download files
"%UV%" cache clean >nul 2>nul

echo.
echo  ======================================================================
echo   SETUP COMPLETE.
echo   Next: double-click "2_RUN on my scans.bat" and pick your MRI scan.
echo  ======================================================================
echo.
pause
exit /b 0

:fail_oldwindows
echo.
echo PROBLEM: this version of Windows is missing curl.exe or tar.exe.
echo Windows 10 (version 1803 or newer) or Windows 11 is required.
goto end_fail

:fail_net
echo.
echo PROBLEM: a download or install step failed. This is usually a network hiccup
echo or a university firewall. Check your internet connection and simply run this
echo setup again: finished steps are skipped, so it picks up where it stopped.
goto end_fail

:fail_verify
echo.
echo PROBLEM: the final check failed (see the messages above). Run this setup
echo again. If it fails a second time, send a screenshot of this window to
echo whoever is helping you.
goto end_fail

:fail
echo.
echo PROBLEM: setup stopped unexpectedly. Run it again; if it fails twice,
echo send a screenshot of this window to whoever is helping you.

:end_fail
echo.
pause
exit /b 1
