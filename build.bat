@echo off
REM ============================================================
REM  build.bat - 使用 WDK 编译 MSR 驱动
REM
REM  前置要求：
REM    1. 安装 Visual Studio 2019/2022 (Community 即可)
REM    2. 安装 Windows Driver Kit (WDK) 10
REM       https://learn.microsoft.com/zh-cn/windows-hardware/drivers/download-the-wdk
REM
REM  使用方法：
REM    打开 "x64 Native Tools Command Prompt for VS"
REM    然后运行 build.bat
REM ============================================================

echo ==========================================
echo   MSR Driver Build Script
echo ==========================================

REM 检查 WDK 是否安装
if not exist "%WDKContentRoot%" (
    echo [错误] 未找到 WDK，请先安装 Windows Driver Kit
    echo 下载: https://learn.microsoft.com/zh-cn/windows-hardware/drivers/download-the-wdk
    exit /b 1
    )

REM 设置输出目录
set OUTPUT_DIR=%~dp0bin\x64
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM 使用 MSBuild 编译
REM 如果你没有 VS 项目文件，可以用命令行直接编译：

echo.
echo 正在编译 msr_drv.c ...
echo.

cl.exe /nologo /W4 /WX /GS- /D NTDDI_VERSION=0x0A000000 ^
    /D _WIN64 /D _AMD64_ /D _NDEBUG /D _KERNEL_MODE ^
    /I"%WDKContentRoot%\Include\10.0.22621.0\km" ^
    /I"%WDKContentRoot%\Include\10.0.22621.0\shared" ^
    /I"%WindowsSdkDir%\Include\10.0.22621.0\ucrt" ^
    /I"%VCToolsInstallDir%\include" ^
    /kernel /Zi /Od /c ^
    /Fo"%OUTPUT_DIR%\msr_drv.obj" ^
    "%~dp0msr_drv.c"

if errorlevel 1 (
    echo [错误] 编译失败
    exit /b 1
)

echo.
echo 正在链接 ...
echo.

link.exe /nologo /DEBUG /DRIVER /ENTRY:DriverEntry ^
    /OUT:"%OUTPUT_DIR%\msr_drv.sys" ^
    /SUBSYSTEM:NATIVE ^
    /MACHINE:X64 ^
    /LIBPATH:"%WDKContentRoot%\Lib\10.0.22621.0\km\x64" ^
    "%OUTPUT_DIR%\msr_drv.obj" ^
    ntoskrnl.lib hal.lib wdfldr.lib

if errorlevel 1 (
    echo [错误] 链接失败
    exit /b 1
)

echo.
echo ==========================================
echo   编译成功！
echo   输出: %OUTPUT_DIR%\msr_drv.sys
echo ==========================================
echo.
echo 下一步：
echo   1. 运行 sign.bat 进行自签名
echo   2. 运行 install.bat 安装驱动
echo.

pause
