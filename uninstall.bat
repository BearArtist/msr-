@echo off
REM ============================================================
REM  uninstall.bat - 卸载 MSR 驱动
REM  必须以管理员身份运行
REM ============================================================

echo ==========================================
echo   MSR Driver Uninstall Script
echo ==========================================

set DRIVER_NAME=msr_drv

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请以管理员身份运行此脚本！
    pause
    exit /b 1
)

echo.
echo 停止驱动...
sc stop %DRIVER_NAME% >nul 2>&1

echo 删除服务...
sc delete %DRIVER_NAME% >nul 2>&1

echo 删除驱动文件...
del /f "%SystemRoot%\System32\drivers\%DRIVER_NAME%.sys" >nul 2>&1

echo.
echo ==========================================
echo   驱动已卸载
echo ==========================================

pause
