@echo off
setlocal
cd /d "%~dp0"

echo Preparing PyInstaller...
python -m pip install PyInstaller --target ".tmp\pyinstaller" --no-cache-dir
if errorlevel 1 (
    echo.
    echo Standard PyPI failed. Trying Tsinghua mirror...
    python -m pip install PyInstaller --target ".tmp\pyinstaller" --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 goto install_failed

echo.
echo Building MyCalendar.exe...
set "PYTHONPATH=%CD%\.tmp\pyinstaller;%CD%\.vendor;%PYTHONPATH%"
python -m PyInstaller --noconfirm --clean --windowed --onefile --name MyCalendar --paths ".vendor" --distpath "dist" --workpath ".tmp\build" --specpath ".tmp" "main.py"
if errorlevel 1 goto build_failed

echo.
echo Done.
echo EXE: "%CD%\dist\MyCalendar.exe"
echo.
pause
exit /b 0

:install_failed
echo.
echo PyInstaller install failed.
echo Please check your network, then run this file again.
echo.
pause
exit /b 1

:build_failed
echo.
echo Build failed. Please send me the error above.
echo.
pause
exit /b 1
