@echo off
chcp 437 >nul
cd /d "%~dp0"
set APP_HOST=0.0.0.0
echo.
echo   HXAI Dangjian - starting Flask (LAN mode) ...
echo.
start "hxai-dangjian" /min ".venv\Scripts\python.exe" -X utf8 run.py
timeout /t 4 >nul
echo   Open on this PC : http://127.0.0.1:5000
echo   Open on phone   : (same campus WiFi, use one of these)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r /c:"IPv4"') do echo       http://%%a:5000
echo   Admin console   : http://127.0.0.1:5000/admin/
echo.
echo   Stop: close the minimized python window in the taskbar.
echo.
pause
