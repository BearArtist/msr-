/*
 * msr_drv.c - MSR Read/Write Driver for Intel Sandy Bridge
 *
 * 专用 MSR 读写驱动，用于调整 CPU 倍频。
 * 仅支持 x64，通过 IOCTL 接口暴露 RDMSR/WRMSR 操作。
 *
 * 编译环境：Windows Driver Kit (WDK) 10
 */

#include <ntddk.h>

#define DEVICE_NAME     L"\\Device\\MsrDrv"
#define SYMLINK_NAME    L"\\DosDevices\\MsrDrv"

/* IOCTL 定义 */
#define IOCTL_RDMSR    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_WRMSR    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

/* 用户态/内核态共享数据结构 */
#pragma pack(push, 1)
typedef struct _MSR_REQUEST {
    UINT32 Register;    /* MSR 地址 */
    UINT64 Value;       /* 读/写的值 */
    NTSTATUS Status;    /* 操作结果 */
} MSR_REQUEST, *PMSR_REQUEST;
#pragma pack(pop)

/* 前置声明 */
DRIVER_UNLOAD DriverUnload;
_Dispatch_type_(IRP_MJ_CREATE)      DRIVER_DISPATCH DriverCreate;
_Dispatch_type_(IRP_MJ_CLOSE)       DRIVER_DISPATCH DriverClose;
_Dispatch_type_(IRP_MJ_DEVICE_CONTROL) DRIVER_DISPATCH DriverDeviceControl;

/*
 * DriverUnload - 卸载时清理
 */
VOID DriverUnload(_In_ PDRIVER_OBJECT DriverObject)
{
    UNICODE_STRING symlink;
    PDEVICE_OBJECT devObj = DriverObject->DeviceObject;

    RtlInitUnicodeString(&symlink, SYMLINK_NAME);
    IoDeleteSymbolicLink(&symlink);

    if (devObj) {
        IoDeleteDevice(devObj);
    }

    DbgPrint("[MsrDrv] Driver unloaded.\n");
}

/*
 * DriverCreate - 打开设备
 */
NTSTATUS DriverCreate(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

/*
 * DriverClose - 关闭设备
 */
NTSTATUS DriverClose(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    Irp->IoStatus.Status = STATUS_SUCCESS;
    Irp->IoStatus.Information = 0;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

/*
 * DriverDeviceControl - 处理 IOCTL 请求
 */
NTSTATUS DriverDeviceControl(_In_ PDEVICE_OBJECT DeviceObject, _Inout_ PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);

    PIO_STACK_LOCATION irpSp = IoGetCurrentIrpStackLocation(Irp);
    NTSTATUS status = STATUS_SUCCESS;
    ULONG_PTR information = 0;
    ULONG ctlCode = irpSp->Parameters.DeviceIoControl.IoControlCode;

    /* 输入/输出缓冲区检查 */
    ULONG inLen = irpSp->Parameters.DeviceIoControl.InputBufferLength;
    ULONG outLen = irpSp->Parameters.DeviceIoControl.OutputBufferLength;

    if (inLen < sizeof(MSR_REQUEST) || outLen < sizeof(MSR_REQUEST)) {
        status = STATUS_BUFFER_TOO_SMALL;
        goto done;
    }

    PMSR_REQUEST req = (PMSR_REQUEST)Irp->AssociatedIrp.SystemBuffer;

    switch (ctlCode) {

    case IOCTL_RDMSR: {
        /*
         * RDMSR 读取指定 MSR 寄存器
         * 输入：req->Register = MSR 地址
         * 输出：req->Value = 读取到的 64 位值
         */
        INT32 cpuInfo[4] = {0};
        UINT64 msrValue = 0;
        UINT32 msrAddr = req->Register;

        __try {
            /*
             * 注意：RDMSR 在当前 CPU 核心执行。
             * 如果需要指定核心，需要先 KeSetSystemAffinityThread。
             * 这里简化为在当前核心执行。
             */
            msrValue = __readmsr(msrAddr);
            req->Value = msrValue;
            req->Status = STATUS_SUCCESS;
            status = STATUS_SUCCESS;
            information = sizeof(MSR_REQUEST);

            DbgPrint("[MsrDrv] RDMSR(0x%03X) = 0x%016llX\n", msrAddr, msrValue);
        }
        __except (EXCEPTION_EXECUTE_HANDLER) {
            req->Status = STATUS_INVALID_PARAMETER;
            status = STATUS_INVALID_PARAMETER;
            information = sizeof(MSR_REQUEST);
            DbgPrint("[MsrDrv] RDMSR(0x%03X) failed: invalid register\n", msrAddr);
        }
        break;
    }

    case IOCTL_WRMSR: {
        /*
         * WRMSR 写入指定 MSR 寄存器
         * 输入：req->Register = MSR 地址, req->Value = 要写入的值
         * Sandy Bridge IA32_PERF_CTL (0x199) bits [15:8] = target ratio
         */
        UINT32 msrAddr = req->Register;
        UINT64 msrValue = req->Value;

        __try {
            __writemsr(msrAddr, msrValue);
            req->Status = STATUS_SUCCESS;
            status = STATUS_SUCCESS;
            information = sizeof(MSR_REQUEST);

            DbgPrint("[MsrDrv] WRMSR(0x%03X, 0x%016llX) OK\n", msrAddr, msrValue);
        }
        __except (EXCEPTION_EXECUTE_HANDLER) {
            req->Status = STATUS_INVALID_PARAMETER;
            status = STATUS_INVALID_PARAMETER;
            information = sizeof(MSR_REQUEST);
            DbgPrint("[MsrDrv] WRMSR(0x%03X, 0x%016llX) failed\n", msrAddr, msrValue);
        }
        break;
    }

    default:
        status = STATUS_INVALID_DEVICE_REQUEST;
        break;
    }

done:
    Irp->IoStatus.Status = status;
    Irp->IoStatus.Information = information;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}

/*
 * DriverEntry - 驱动入口
 */
NTSTATUS DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
{
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS status;
    PDEVICE_OBJECT devObj = NULL;
    UNICODE_STRING devName, symlink;

    RtlInitUnicodeString(&devName, DEVICE_NAME);
    RtlInitUnicodeString(&symlink, SYMLINK_NAME);

    /* 创建设备对象 */
    status = IoCreateDevice(
        DriverObject,
        0,                  /* 无扩展 */
        &devName,
        FILE_DEVICE_UNKNOWN,
        FILE_DEVICE_SECURE_OPEN,
        FALSE,
        &devObj
    );

    if (!NT_SUCCESS(status)) {
        DbgPrint("[MsrDrv] IoCreateDevice failed: 0x%08X\n", status);
        return status;
    }

    /* 创建符号链接 */
    status = IoCreateSymbolicLink(&symlink, &devName);
    if (!NT_SUCCESS(status)) {
        DbgPrint("[MsrDrv] IoCreateSymbolicLink failed: 0x%08X\n", status);
        IoDeleteDevice(devObj);
        return status;
    }

    /* 设置分发函数 */
    DriverObject->MajorFunction[IRP_MJ_CREATE]         = DriverCreate;
    DriverObject->MajorFunction[IRP_MJ_CLOSE]          = DriverClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = DriverDeviceControl;
    DriverObject->DriverUnload                         = DriverUnload;

    /* 设置缓冲区 I/O */
    devObj->Flags |= DO_BUFFERED_IO;

    DbgPrint("[MsrDrv] Driver loaded. Device: %wZ\n", &devName);

    return STATUS_SUCCESS;
}
