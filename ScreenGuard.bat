@echo off
rem Double-click to launch the ScreenGuard app.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m app.gui %*
if errorlevel 1 pause
