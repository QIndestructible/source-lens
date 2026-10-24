@echo off
setlocal
cd /d "%~dp0"

set "PY="

rem 1) prefer the Windows launcher
where py >nul 2>nul && set "PY=py -3"

rem 2) then python on PATH
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)

rem 3) then common install locations
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
  )
)
if not defined PY if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"

if not defined PY (
  echo.
  echo   Python not found.
  echo.
  echo   Install Python 3.9+ from https://www.python.org/downloads/
  echo   During setup, tick "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo   Using: %PY%
echo   Starting local server, browser will open in a second...
echo.

%PY% app.py %*
set "CODE=%ERRORLEVEL%"

echo.
if not "%CODE%"=="0" (
  echo   Server exited with code %CODE%.
  echo   Copy the message above if you need help.
) else (
  echo   Server stopped.
)
echo.
pause
