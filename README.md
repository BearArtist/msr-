# MSR Driver - Sandy Bridge 倍频调整工具

专用 MSR (Model Specific Register) 读写内核驱动，用于 Intel Sandy Bridge (二代酷睿) 平台的倍频调整。

## 目录结构

```
msr_driver/
├── msr_drv.c           # 内核驱动源码 (C)
├── msr_drv.inf         # 驱动安装信息文件
├── msr_client.py       # Python 客户端 (ctypes)
├── build.bat           # 编译脚本 (需要 WDK)
├── sign.bat            # 自签名脚本
├── install.bat         # 安装驱动脚本
├── uninstall.bat       # 卸载驱动脚本
└── README.md           # 本文件
```

## 前置要求

### 编译环境
1. **Visual Studio 2019/2022** (Community 版即可)
   - 安装 "C++ 桌面开发" 工作负载
2. **Windows Driver Kit (WDK) 10**
   - 下载: https://learn.microsoft.com/zh-cn/windows-hardware/drivers/download-the-wdk
3. **Windows SDK 10**

### 运行环境
- Windows 10/11 x64
- 管理员权限
- Intel Sandy Bridge CPU (2代酷睿)

## 编译步骤

### 1. 编译驱动

打开 **"x64 Native Tools Command Prompt for VS"**，然后：

```cmd
cd msr_driver
build.bat
```

输出: `bin\x64\msr_drv.sys`

### 2. 自签名

```cmd
sign.bat
```

此脚本会：
- 创建自签名代码签名证书
- 使用 SHA256 签名驱动文件
- 导出证书到 `bin\x64\MsrDrvCert.pfx`

### 3. 启用测试签名模式

**必须执行此步骤**，否则 Windows 11 不会加载自签名驱动：

```cmd
# 以管理员身份运行
bcdedit /set testsigning on
# 重启电脑
shutdown /r /t 0
```

### 4. 安装驱动

```cmd
# 以管理员身份运行
install.bat
```

### 5. 使用 Python 调整倍频

```cmd
# 以管理员身份运行
python msr_client.py
```

## Python API 用法

```python
from msr_client import MsrDriver, get_current_ratio, set_target_ratio

# 打开驱动
with MsrDriver() as msr:
    # 读取当前倍频
    current = get_current_ratio(msr)
    print(f"当前倍频: {current}x")

    # 设置目标倍频 (例如 38x)
    set_target_ratio(msr, 38)

    # 读取任意 MSR 寄存器
    val = msr.read(0x198)  # IA32_PERF_STATUS
    print(f"PERF_STATUS: 0x{val:016X}")

    # 写入任意 MSR 寄存器
    msr.write(0x199, val)  # IA32_PERF_CTL
```

### 关键 MSR 寄存器 (Sandy Bridge)

| 地址 | 名称 | 读/写 | 说明 |
|------|------|-------|------|
| `0x198` | IA32_PERF_STATUS | R | 当前倍频 (bits 15:8) |
| `0x199` | IA32_PERF_CTL | W | 目标倍频 (bits 15:8) |
| `0x1AD` | MSR_TURBO_RATIO_LIMIT | R/W | Turbo 倍频上限 |
| `0xCE` | MSR_PLATFORM_INFO | R | 最大非 Turbo 倍频 |
| `0x610` | MSR_PKG_POWER_LIMIT | R/W | 功耗墙 PL1/PL2 |

### 倍频调整原理

Sandy Bridge 的倍频通过 `IA32_PERF_CTL` (0x199) 寄存器控制：

```
IA32_PERF_CTL (0x199) 64-bit:
┌─────────────────────────────────────────────────────────────┐
│ 63      32 │ 31    16 │ 15     8 │ 7        0 │
│  reserved  │  flags   │ TARGET   │  reserved  │
│            │          │  RATIO   │            │
└─────────────────────────────────────────────────────────────┘
                    ↑
            bits [15:8] = 目标倍频值
            例如: 0x26 = 38x, 0x28 = 40x
```

## 安全注意事项

1. **过高的倍频可能导致系统不稳定或蓝屏**
   - 建议每次增加 1x，逐步测试稳定性
   - 使用 Prime95 / AIDA64 进行压力测试

2. **过热风险**
   - 超频前确保散热良好
   - 使用 HWMonitor 监控温度

3. **电压不要超过安全范围**
   - Sandy Bridge 推荐最大 1.35V VCore

## 卸载

```cmd
# 以管理员身份运行
uninstall.bat

# 如需关闭测试签名模式
bcdedit /set testsigning off
# 重启
```

## 故障排除

### "无法打开设备" 错误
- 确认以管理员身份运行
- 确认驱动已加载: `sc query msr_drv`
- 确认测试签名模式已开启

### 驱动加载失败
- 检查签名是否有效: `signtool verify /pa bin\x64\msr_drv.sys`
- 确认 `bcdedit /set testsigning on` 已执行并已重启

### 倍频设置不生效
- 某些主板可能在 BIOS 中锁定了倍频
- 检查 BIOS 中是否有 "CPU Ratio" 或 "Overclock" 相关设置
- 确认 CPU 支持非 K 超频 (部分 Sandy Bridge 可以)

## 关于签名

本驱动使用自签名证书，**不受微软信任**。在正式环境中：

- **最佳方案**: 购买 EV 代码签名证书 (~$200-400/年)
  - 受微软信任，无需开启测试签名模式
  - 推荐 DigiCert / Sectigo / GlobalSign
- **开发/测试**: 使用测试签名模式 (本方案)
- **临时使用**: 每次启动时 F8 禁用签名强制
