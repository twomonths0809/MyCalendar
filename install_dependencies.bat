@echo off
cd /d "%~dp0"
echo Installing PySide6 into this project...
python -m pip install PySide6 --target .vendor
echo.
echo Done. You can run run_calendar.bat now.
pause
