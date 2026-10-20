@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================================
echo     AI AVATAR STUDIO - KHỞI TẠO HỆ THỐNG TỰ ĐỘNG TRÊN MÁY MỚI
echo ====================================================================
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Chưa tìm thấy Python trên máy tính.
    echo Vui lòng cài đặt Python 3.10 hoặc 3.11 (nhớ tích chọn 'Add Python to PATH').
    pause
    exit /b 1
)
python tools\setup_new_machine.py
pause
