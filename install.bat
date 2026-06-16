@echo off
REM ============================================================
REM  install.bat - 安装并加载 MSR 驱动
REM  必须以管理员身份运行
REM ============================================================

echo ==========================================
echo   MSR Driver Install Script
echo ==========================================

set OUTPUT_DIR=%~dp0bin\x64
set SYS_FILE=%OUTPUT_DIR%\msr_drv.sys
set DRIVER_NAME=msr_drv

REM 检查管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请以管理员身份运行此脚本！
    pause
    exit /b 1
)

REM 检查驱动文件
if not exist "%SYS_FILE%" (
    echo [错误] 未找到 %SYS_FILE%
    echo 请先运行 build.bat 和 sign.bat
    pause
    exit /b 1
)

echo.
echo [步骤 1/2] 复制驱动到系统目录...
echo.

copy /Y "%SYS_FILE%" "%SystemRoot%\System32\drivers\%DRIVER_NAME%.sys"
if errorlevel 1 (
    echo [错误] 复制失败
    pause
    exit /b 1
)

echo.
echo [步骤 2/2] 注册并启动驱动...
echo.

REM 使用 sc 命令创建服务
sc create %DRIVER_NAME% type= kernel start= demand binPath= "%SystemRoot%\System32\drivers\%DRIVER_NAME%.sys" DisplayName= "MSR Read/Write Driver"
if errorlevel 1 (
    echo [错误] 创建服务失败
    pause
    exit /b 1
)

sc start %DRIVER_NAME%
if errorlevel 1 (
    echo [错误] 启动驱动失败
    echo 可能原因：
    echo   1. 驱动未签名或签名不受信任
    echo   2. 需要开启测试签名模式: bcdedit /set testsigning on
    sc delete %DRIVER_NAME% >nul 2>&1
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   驱动安装并启动成功！
echo   设备路径: \\.\MsrDrv
echo ==========================================
echo.
echo 现在可以运行 Python 脚本了：
echo   python msr_client.py
echo.

pause
