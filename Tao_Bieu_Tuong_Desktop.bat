@echo off
chcp 65001 >nul
echo Đang tạo biểu tượng AI Avatar Studio ngoài màn hình Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create_desktop_shortcut.ps1"
echo.
echo Hoàn tất! Bạn có thể ra màn hình Desktop bấm vào "AI Avatar Studio" để sử dụng.
pause
