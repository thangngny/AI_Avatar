@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================================
echo     AI AVATAR STUDIO - MÁY CHỦ TRUYỀN DỮ LIỆU SANG MÁY MỚI (LAN)
echo ====================================================================
python tools\lan_sync_server.py
pause
