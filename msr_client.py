"""
msr_client.py - MSR 驱动 Python 客户端

通过 DeviceIoControl 与内核驱动通信，实现 MSR 寄存器读写。
用于 Intel Sandy Bridge (二代酷睿) 倍频调整。

使用方法：
    # 需要管理员权限运行
    from msr_client import MsrDriver

    with MsrDriver() as msr:
        # 读取当前倍频状态
        val = msr.read(0x198)   # IA32_PERF_STATUS
        print(f"当前倍频: {(val >> 8) & 0xFF}")

        # 设置目标倍频 (例如 40x)
        ratio = 40
        new_val = (val & ~0xFF00) | (ratio << 8)
        msr.write(0x199, new_val)  # IA32_PERF_CTL
"""

import ctypes
import ctypes.wintypes as wintypes
import struct
import sys
import os
import time
from contextlib import contextmanager

# Windows API 常量
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
FILE_DEVICE_UNKNOWN = 0x22
METHOD_BUFFERED = 0
FILE_ANY_ACCESS = 0
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

# IOCTL 定义（与驱动中一致）
def CTL_CODE(DeviceType, Function, Method, Access):
    return (DeviceType << 16) | (Access << 14) | (Function << 2) | Method

IOCTL_RDMSR = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
IOCTL_WRMSR = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

# MSR 请求结构体（与驱动中一致）
class MSR_REQUEST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Register", ctypes.c_uint32),   # MSR 地址
        ("Value",    ctypes.c_uint64),   # 读/写的值
        ("Status",   ctypes.c_int32),    # NTSTATUS 结果
    ]

# ============================================================
# Sandy Bridge 常用 MSR 寄存器
# ============================================================
MSR_IA32_PERF_CTL       = 0x199   # 目标性能状态（写入倍频）
MSR_IA32_PERF_STATUS    = 0x198   # 当前性能状态（读取倍频）
MSR_TURBO_RATIO_LIMIT   = 0x1AD   # Turbo 倍频上限
MSR_PKG_POWER_LIMIT     = 0x610   # 功耗墙 PL1/PL2
MSR_PLATFORM_INFO       = 0xCE    # 平台信息（最大非 turbo 倍频）
MSR_TEMPERATURE_TARGET   = 0x1A2   # 温度目标


class MsrDriver:
    """MSR 驱动客户端"""

    def __init__(self, device_path=r"\\.\MsrDrv"):
        """
        初始化并打开驱动设备。

        Args:
            device_path: 设备路径，默认 \\.\MsrDrv
        """
        self.device_path = device_path
        self.handle = None
        self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # 声明 API 函数原型
        self._CreateFile = self._kernel32.CreateFileW
        self._CreateFile.argtypes = [
            wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        self._CreateFile.restype = wintypes.HANDLE

        self._DeviceIoControl = self._kernel32.DeviceIoControl
        self._DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
        ]
        self._DeviceIoControl.restype = wintypes.BOOL

        self._CloseHandle = self._kernel32.CloseHandle
        self._CloseHandle.argtypes = [wintypes.HANDLE]
        self._CloseHandle.restype = wintypes.BOOL

    def open(self):
        """打开驱动设备"""
        self.handle = self._CreateFile(
            self.device_path,
            GENERIC_READ | GENERIC_WRITE,
            0, None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )
        if self.handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            raise OSError(f"无法打开设备 {self.device_path}，错误码: {err}\n"
                          f"请确认：1) 以管理员身份运行  2) 驱动已加载")

    def close(self):
        """关闭设备"""
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            self._CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def read(self, register: int) -> int:
        """
        读取 MSR 寄存器。

        Args:
            register: MSR 地址 (如 0x199)

        Returns:
            64 位寄存器值
        """
        req = MSR_REQUEST()
        req.Register = register
        req.Value = 0
        req.Status = 0

        bytes_returned = wintypes.DWORD(0)
        ok = self._DeviceIoControl(
            self.handle,
            IOCTL_RDMSR,
            ctypes.byref(req), ctypes.sizeof(req),
            ctypes.byref(req), ctypes.sizeof(req),
            ctypes.byref(bytes_returned),
            None
        )

        if not ok:
            err = ctypes.get_last_error()
            raise OSError(f"IOCTL_RDMSR 失败，错误码: {err}")

        if req.Status != 0:
            raise OSError(f"RDMSR(0x{register:03X}) 内核返回错误: 0x{req.Status:08X}")

        return req.Value

    def write(self, register: int, value: int):
        """
        写入 MSR 寄存器。

        Args:
            register: MSR 地址 (如 0x199)
            value: 要写入的 64 位值
        """
        req = MSR_REQUEST()
        req.Register = register
        req.Value = value & 0xFFFFFFFFFFFFFFFF
        req.Status = 0

        bytes_returned = wintypes.DWORD(0)
        ok = self._DeviceIoControl(
            self.handle,
            IOCTL_WRMSR,
            ctypes.byref(req), ctypes.sizeof(req),
            ctypes.byref(req), ctypes.sizeof(req),
            ctypes.byref(bytes_returned),
            None
        )

        if not ok:
            err = ctypes.get_last_error()
            raise OSError(f"IOCTL_WRMSR 失败，错误码: {err}")

        if req.Status != 0:
            raise OSError(f"WRMSR(0x{register:03X}, 0x{value:016X}) 内核返回错误: 0x{req.Status:08X}")


# ============================================================
# Sandy Bridge 倍频操作工具函数
# ============================================================

def get_current_ratio(msr: MsrDriver) -> int:
    """获取当前倍频"""
    val = msr.read(MSR_IA32_PERF_STATUS)
    return (val >> 8) & 0xFF


def get_max_turbo_ratio(msr: MsrDriver) -> int:
    """获取最大 Turbo 倍频"""
    val = msr.read(MSR_TURBO_RATIO_LIMIT)
    return val & 0xFF


def get_platform_info(msr: MsrDriver) -> dict:
    """获取平台信息"""
    val = msr.read(MSR_PLATFORM_INFO)
    max_non_turbo = (val >> 8) & 0xFF
    return {
        "max_non_turbo_ratio": max_non_turbo,
        "raw": val
    }


def set_target_ratio(msr: MsrDriver, ratio: int):
    """
    设置目标倍频。

    Sandy Bridge IA32_PERF_CTL (0x199):
        bits [15:8] = target ratio
        bit [32]    = turbo engage (可选)

    Args:
        msr: MsrDriver 实例
        ratio: 目标倍频 (如 40 表示 40x)
    """
    # 先读当前值，保留其他位
    current = msr.read(MSR_IA32_PERF_CTL)
    # 清除 bits [15:8]，设置新倍频
    new_val = (current & ~0xFF00) | ((ratio & 0xFF) << 8)
    msr.write(MSR_IA32_PERF_CTL, new_val)
    print(f"[OK] 目标倍频已设置为 {ratio}x (0x199 = 0x{new_val:016X})")


def set_turbo_ratio_limit(msr: MsrDriver, ratio: int):
    """
    设置 Turbo 倍频上限。

    Sandy Bridge MSR_TURBO_RATIO_LIMIT (0x1AD):
        bits [7:0] = 1C 最大倍频
        bits [15:8] = 2C 最大倍频
        ...

    Args:
        ratio: 目标 Turbo 倍频上限
    """
    current = msr.read(MSR_TURBO_RATIO_LIMIT)
    # 设置所有核心的 turbo 上限为相同值
    new_val = ratio & 0xFF
    new_val |= (ratio & 0xFF) << 8
    new_val |= (ratio & 0xFF) << 16
    new_val |= (ratio & 0xFF) << 24
    # 保留高位
    new_val |= (current & 0xFFFFFFFF00000000)
    msr.write(MSR_TURBO_RATIO_LIMIT, new_val)
    print(f"[OK] Turbo 倍频上限已设置为 {ratio}x (0x1AD = 0x{new_val:016X})")


# ============================================================
# 示例：调整倍频
# ============================================================

def demo():
    """交互式倍频调整演示"""
    print("=" * 50)
    print("  Sandy Bridge MSR 倍频调整工具")
    print("=" * 50)

    # 检查管理员权限
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("[错误] 请以管理员身份运行此脚本！")
            sys.exit(1)
    except Exception:
        pass

    with MsrDriver() as msr:
        # 读取平台信息
        info = get_platform_info(msr)
        print(f"\n最大非 Turbo 倍频: {info['max_non_turbo_ratio']}x")

        # 读取当前状态
        current = get_current_ratio(msr)
        print(f"当前倍频: {current}x")

        try:
            max_turbo = get_max_turbo_ratio(msr)
            print(f"最大 Turbo 倍频: {max_turbo}x")
        except Exception as e:
            print(f"读取 Turbo 限制失败: {e}")

        # 交互式调整
        print("\n--- 调整倍频 ---")
        print("输入目标倍频 (如 38 表示 38x)，输入 q 退出")

        while True:
            try:
                raw = input("\n目标倍频> ").strip()
                if raw.lower() == 'q':
                    break

                target = int(raw)

                # 安全范围检查 (Sandy Bridge 通常 16-60)
                if target < 16 or target > 60:
                    print(f"[警告] 倍频 {target}x 可能超出安全范围 (16-60)")
                    confirm = input("继续？(y/n) ").strip().lower()
                    if confirm != 'y':
                        continue

                # 设置倍频
                set_target_ratio(msr, target)

                # 读回验证
                time.sleep(0.1)
                actual = get_current_ratio(msr)
                print(f"读回验证: {actual}x")

            except ValueError:
                print("请输入有效的数字")
            except KeyboardInterrupt:
                break
            except OSError as e:
                print(f"[错误] {e}")

    print("\n完成。")


if __name__ == "__main__":
    demo()
