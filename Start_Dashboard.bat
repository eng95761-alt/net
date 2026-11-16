@echo off
title MikroTik RB4011 Smart Control Platform
color 0b
echo =====================================================================
echo           MikroTik RB4011 Smart Control Platform (MSCP)
echo           لوحة المراقبة والتحكم الذكية لمايكروتك RB4011
echo =====================================================================
echo.
echo [*] Checking Python environment...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not installed or not in PATH!
    pause
    exit /b
)

cd /d "c:\Users\DIGITAL WORLD\Desktop\4011\dashboard"

echo [*] Starting MSCP Backend Server on port 8000...
start "" http://localhost:8000
python backend.py

pause
