@echo off
REM ============================================================
REM  sign.bat - 自签名驱动
REM
REM  此脚本创建自签名证书并签名驱动文件。
REM  必须以管理员身份运行。
REM
REM  ⚠️ 自签名驱动在 Windows 11 上需要：
REM    - 方法 A: 开启测试签名模式 (推荐)
REM      bcdedit /set testsigning on
REM    - 方法 B: 重启时按 F8 禁用驱动签名强制
REM    - 方法 C: 将证书导入到 "受信任的根证书颁发机构"
REM ============================================================

echo ==========================================
echo   MSR Driver Self-Signing Script
echo ==========================================

set OUTPUT_DIR=%~dp0bin\x64
set CERT_NAME=MsrDrvCert
set PFX_FILE=%OUTPUT_DIR%\%CERT_NAME%.pfx
set SYS_FILE=%OUTPUT_DIR%\msr_drv.sys

REM 检查驱动文件是否存在
if not exist "%SYS_FILE%" (
    echo [错误] 未找到 %SYS_FILE%
    echo 请先运行 build.bat 编译驱动
    pause
    exit /b 1
)

REM 查找 signtool
set SIGNTOOL=
for /f "tokens=*" %%i in ('where /r "%WindowsSdkDir%" signtool.exe 2^>nul') do set SIGNTOOL=%%i
if "%SIGNTOOL%"=="" (
    for /f "tokens=*" %%i in ('where /r "%ProgramFiles(x86)%\Windows Kits" signtool.exe 2^>nul') do set SIGNTOOL=%%i
)
if "%SIGNTOOL%"=="" (
    echo [错误] 未找到 signtool.exe
    echo 请安装 Windows SDK
    pause
    exit /b 1
)

REM 查找 makecert (可选)
set MAKECERT=
for /f "tokens=*" %%i in ('where /r "%WindowsSdkDir%" makecert.exe 2^>nul') do set MAKECERT=%%i

echo.
echo [步骤 1/3] 创建自签名证书...
echo.

REM 使用 PowerShell 创建自签名证书（比 makecert 更通用）
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=MsrDrvCert' -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddYears(5) -HashAlgorithm SHA256; " ^
    "$pwd = ConvertTo-SecureString -String 'MsrDrv123' -Force -AsPlainText; " ^
    "Export-PfxCertificate -Cert $cert -FilePath '%PFX_FILE%' -Password $pwd; " ^
    "Write-Host '证书指纹: ' $cert.Thumbprint; " ^
    "Write-Host '证书已导出: %PFX_FILE%'"

if errorlevel 1 (
    echo [错误] 创建证书失败
    pause
    exit /b 1
)

echo.
echo [步骤 2/3] 签名驱动文件...
echo.

"%SIGNTOOL%" sign /f "%PFX_FILE%" /p MsrDrv123 /tr http://timestamp.digicert.com /td sha256 /fd sha256 "%SYS_FILE%"

if errorlevel 1 (
    echo [警告] 签名失败，尝试不带时间戳签名...
    "%SIGNTOOL%" sign /f "%PFX_FILE%" /p MsrDrv123 /fd sha256 "%SYS_FILE%"
    if errorlevel 1 (
        echo [错误] 签名失败
        pause
        exit /b 1
    )
)

echo.
echo [步骤 3/3] 验证签名...
echo.

"%SIGNTOOL%" verify /pa "%SYS_FILE%"
if errorlevel 1 (
    echo [警告] 验证失败 - 这在自签名时是正常的
    echo         需要将证书导入到受信任的存储区
)

echo.
echo ==========================================
echo   签名完成！
echo ==========================================
echo.
echo 后续步骤 (选择一种方式让 Windows 加载自签名驱动):
echo.
echo 【方法 A - 测试签名模式 (推荐)】
echo   以管理员身份运行：
echo   bcdedit /set testsigning on
echo   然后重启电脑
echo.
echo 【方法 B - 导入证书到受信任根】
echo   1. 双击 %PFX_FILE% (密码: MsrDrv123)
echo   2. 导入到 "本地计算机" > "受信任的根证书颁发机构"
echo   3. 重启电脑
echo.
echo 【方法 C - 每次启动时禁用签名强制】
echo   重启时按 F8 > 禁用驱动程序强制签名
echo   (仅当次启动有效)
echo.

pause
