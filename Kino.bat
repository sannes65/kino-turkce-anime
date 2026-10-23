@echo off
rem Kino'yu baslat (Windows: cift tikla). Durdurmak icin: Kino.bat stop
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 start.py %*
) else (
  python start.py %*
)
if errorlevel 1 pause
