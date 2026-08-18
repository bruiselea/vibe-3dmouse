#include <ntddk.h>
#include <wdf.h>
#include <vhf.h>
#include <ntstrsafe.h>

#define CODEX_VID 0x303A
#define CODEX_PID 0x8360
#define CODEX_VERSION 0x0100
#define REPORT_ID 0x06
#define REPORT_DATA_SIZE 63
#define REPORT_SIZE 64
#define RPC_CHUNK_SIZE 61
#define RPC_BUFFER_SIZE 2048

typedef struct _CODEX_REPORT {
    UCHAR ReportId;
    UCHAR Data[REPORT_DATA_SIZE];
} CODEX_REPORT, *PCODEX_REPORT;

typedef struct _DEVICE_CONTEXT {
    VHFHANDLE VhfHandle;
    WDFSPINLOCK RpcLock;
    ULONG RpcLength;
    CHAR RpcBuffer[RPC_BUFFER_SIZE];
} DEVICE_CONTEXT, *PDEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DEVICE_CONTEXT, DeviceGetContext);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD CodexEvtDeviceAdd;
EVT_WDF_OBJECT_CONTEXT_CLEANUP CodexEvtDeviceCleanup;
EVT_VHF_ASYNC_OPERATION CodexEvtWriteReport;
EVT_VHF_ASYNC_OPERATION CodexEvtGetFeature;
EVT_VHF_ASYNC_OPERATION CodexEvtSetFeature;
EVT_VHF_ASYNC_OPERATION CodexEvtGetInputReport;

static UCHAR g_ReportDescriptor[] = {
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01, 0x05, 0x07, 0x19, 0xE0,
    0x29, 0xE7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00,
    0x25, 0xA4, 0x05, 0x07, 0x19, 0x00, 0x29, 0xA4, 0x81, 0x00, 0xC0,

    0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x02, 0x75, 0x10, 0x95, 0x01,
    0x15, 0x00, 0x26, 0xFF, 0x07, 0x19, 0x00, 0x2A, 0xFF, 0x07, 0x81, 0x00,
    0xC0,

    0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x85, 0x03, 0x09, 0x01, 0xA1, 0x00,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x05, 0x15, 0x00, 0x25, 0x01, 0x95, 0x05,
    0x75, 0x01, 0x81, 0x02, 0x95, 0x01, 0x75, 0x03, 0x81, 0x01, 0x05, 0x01,
    0x09, 0x30, 0x09, 0x31, 0x15, 0x81, 0x25, 0x7F, 0x95, 0x02, 0x75, 0x08,
    0x81, 0x06, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x95, 0x01, 0x75, 0x08,
    0x81, 0x06, 0x05, 0x0C, 0x0A, 0x38, 0x02, 0x15, 0x81, 0x25, 0x7F, 0x95,
    0x01, 0x75, 0x08, 0x81, 0x06, 0xC0, 0xC0,

    0x06, 0x00, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x06, 0x09, 0x02, 0x15,
    0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0x81, 0x02, 0x09, 0x03,
    0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0x91, 0x02, 0x09,
    0x04, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0xB1, 0x02,
    0xC0,
};

static WCHAR g_HardwareIds[] =
    L"HID\\VID_303A&PID_8360\0"
    L"HID\\VID_303A&PID_8360\0";
static WCHAR g_InstanceId[] = L"SPACEMOUSE-CODEX-0001";

static BOOLEAN
AsciiEquals(_In_z_ const CHAR* left, _In_z_ const CHAR* right)
{
    ULONG i = 0;
    while (left[i] != '\0' && right[i] != '\0' && left[i] == right[i]) {
        i++;
    }
    return left[i] == '\0' && right[i] == '\0';
}

static NTSTATUS
FindJsonStringField(
    _In_reads_bytes_(length) const CHAR* json,
    _In_ ULONG length,
    _In_z_ const CHAR* field,
    _Out_writes_z_(capacity) CHAR* output,
    _In_ ULONG capacity)
{
    ULONG i;
    ULONG fieldLength = 0;
    while (field[fieldLength] != '\0') {
        fieldLength++;
    }

    for (i = 0; i + fieldLength + 2 < length; i++) {
        ULONG cursor;
        ULONG outputLength = 0;
        if (json[i] != '"' ||
            !RtlEqualMemory(json + i + 1, field, fieldLength) ||
            json[i + fieldLength + 1] != '"') {
            continue;
        }
        cursor = i + fieldLength + 2;
        while (cursor < length &&
               (json[cursor] == ' ' || json[cursor] == '\t' || json[cursor] == ':')) {
            cursor++;
        }
        if (cursor >= length || json[cursor] != '"') {
            continue;
        }
        cursor++;
        while (cursor < length && json[cursor] != '"') {
            if (outputLength + 1 >= capacity) {
                return STATUS_BUFFER_TOO_SMALL;
            }
            output[outputLength++] = json[cursor++];
        }
        if (cursor >= length) {
            return STATUS_INVALID_PARAMETER;
        }
        output[outputLength] = '\0';
        return STATUS_SUCCESS;
    }
    return STATUS_NOT_FOUND;
}

static NTSTATUS
FindJsonIntegerField(
    _In_reads_bytes_(length) const CHAR* json,
    _In_ ULONG length,
    _In_z_ const CHAR* field,
    _Out_ LONG* result)
{
    ULONG i;
    ULONG fieldLength = 0;
    while (field[fieldLength] != '\0') {
        fieldLength++;
    }

    for (i = 0; i + fieldLength + 2 < length; i++) {
        ULONG cursor;
        LONG value = 0;
        BOOLEAN negative = FALSE;
        BOOLEAN foundDigit = FALSE;
        if (json[i] != '"' ||
            !RtlEqualMemory(json + i + 1, field, fieldLength) ||
            json[i + fieldLength + 1] != '"') {
            continue;
        }
        cursor = i + fieldLength + 2;
        while (cursor < length &&
               (json[cursor] == ' ' || json[cursor] == '\t' || json[cursor] == ':')) {
            cursor++;
        }
        if (cursor < length && json[cursor] == '-') {
            negative = TRUE;
            cursor++;
        }
        while (cursor < length && json[cursor] >= '0' && json[cursor] <= '9') {
            foundDigit = TRUE;
            value = value * 10 + (json[cursor] - '0');
            cursor++;
        }
        if (foundDigit) {
            *result = negative ? -value : value;
            return STATUS_SUCCESS;
        }
    }
    return STATUS_NOT_FOUND;
}

static NTSTATUS
SubmitInputReport(_In_ PDEVICE_CONTEXT context, _In_ PCODEX_REPORT report)
{
    HID_XFER_PACKET packet;
    packet.reportBuffer = (PUCHAR)report;
    packet.reportBufferLen = sizeof(*report);
    packet.reportId = REPORT_ID;
    return VhfReadReportSubmit(context->VhfHandle, &packet);
}

static NTSTATUS
SendFramedJson(
    _In_ PDEVICE_CONTEXT context,
    _In_reads_bytes_(length) const CHAR* json,
    _In_ ULONG length)
{
    ULONG offset = 0;
    NTSTATUS status = STATUS_SUCCESS;
    while (offset < length) {
        CODEX_REPORT report;
        ULONG remaining = length - offset;
        ULONG chunk = remaining > RPC_CHUNK_SIZE ? RPC_CHUNK_SIZE : remaining;
        RtlZeroMemory(&report, sizeof(report));
        report.ReportId = REPORT_ID;
        report.Data[0] = 2;
        report.Data[1] = (UCHAR)chunk;
        RtlCopyMemory(&report.Data[2], json + offset, chunk);
        status = SubmitInputReport(context, &report);
        if (!NT_SUCCESS(status)) {
            return status;
        }
        offset += chunk;
    }
    return status;
}

static NTSTATUS
ProcessRpcMessage(
    _In_ PDEVICE_CONTEXT context,
    _In_reads_bytes_(length) const CHAR* json,
    _In_ ULONG length)
{
    CHAR method[64];
    CHAR response[512];
    LONG id;
    NTSTATUS status;
    size_t responseLength = 0;

    status = FindJsonStringField(json, length, "method", method, sizeof(method));
    if (!NT_SUCCESS(status)) {
        status = FindJsonStringField(json, length, "m", method, sizeof(method));
    }
    if (!NT_SUCCESS(status)) {
        return STATUS_SUCCESS;
    }
    status = FindJsonIntegerField(json, length, "id", &id);
    if (!NT_SUCCESS(status)) {
        status = FindJsonIntegerField(json, length, "i", &id);
    }
    if (!NT_SUCCESS(status) || id < 0) {
        return STATUS_SUCCESS;
    }

    if (AsciiEquals(method, "device.status")) {
        status = RtlStringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"version\":\"v1.0\",\"profile_index\":0,\"layer_index\":1,\"battery\":100,\"is_charging\":false}}\r\n",
            id,
            method);
    } else if (AsciiEquals(method, "sys.version")) {
        status = RtlStringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"version\":\"v1.0\"}}\r\n",
            id,
            method);
    } else {
        status = RtlStringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"ok\":1}}\r\n",
            id,
            method);
    }
    if (!NT_SUCCESS(status)) {
        return status;
    }
    status = RtlStringCbLengthA(response, sizeof(response), &responseLength);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    return SendFramedJson(context, response, (ULONG)responseLength);
}

static NTSTATUS
HandleOutputReport(
    _In_ PDEVICE_CONTEXT context,
    _In_ PHID_XFER_PACKET packet)
{
    CODEX_REPORT report;
    PUCHAR data;
    ULONG dataLength;
    ULONG chunkLength;
    CHAR method[64];
    CHAR completeRpc[RPC_BUFFER_SIZE];
    ULONG completeLength = 0;
    NTSTATUS status;

    if (packet->reportId != REPORT_ID || packet->reportBuffer == NULL) {
        return STATUS_INVALID_PARAMETER;
    }
    if (packet->reportBufferLen >= REPORT_SIZE && packet->reportBuffer[0] == REPORT_ID) {
        data = packet->reportBuffer + 1;
        dataLength = packet->reportBufferLen - 1;
    } else {
        data = packet->reportBuffer;
        dataLength = packet->reportBufferLen;
    }
    if (dataLength < REPORT_DATA_SIZE || data[0] != 2) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    chunkLength = data[1];
    if (chunkLength > RPC_CHUNK_SIZE || chunkLength > dataLength - 2) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    status = FindJsonStringField(
        (const CHAR*)&data[2], chunkLength, "m", method, sizeof(method));
    if (NT_SUCCESS(status) &&
        (AsciiEquals(method, "v.oai.hid") || AsciiEquals(method, "v.oai.rad"))) {
        RtlZeroMemory(&report, sizeof(report));
        report.ReportId = REPORT_ID;
        RtlCopyMemory(report.Data, data, REPORT_DATA_SIZE);
        return SubmitInputReport(context, &report);
    }

    WdfSpinLockAcquire(context->RpcLock);
    if (context->RpcLength + chunkLength > sizeof(context->RpcBuffer)) {
        context->RpcLength = 0;
        WdfSpinLockRelease(context->RpcLock);
        return STATUS_BUFFER_OVERFLOW;
    }
    RtlCopyMemory(context->RpcBuffer + context->RpcLength, &data[2], chunkLength);
    context->RpcLength += chunkLength;
    /* JSON-RPC HID requests are not newline terminated. */
    if (context->RpcLength > 0 &&
        (chunkLength < RPC_CHUNK_LENGTH ||
         context->RpcBuffer[context->RpcLength - 1] == '\n' ||
         context->RpcBuffer[context->RpcLength - 1] == '\r')) {
        completeLength = context->RpcLength;
        RtlCopyMemory(completeRpc, context->RpcBuffer, completeLength);
        context->RpcLength = 0;
        RtlZeroMemory(context->RpcBuffer, sizeof(context->RpcBuffer));
    }
    WdfSpinLockRelease(context->RpcLock);

    if (completeLength > 0) {
        return ProcessRpcMessage(context, completeRpc, completeLength);
    }
    return STATUS_SUCCESS;
}

VOID
CodexEvtWriteReport(
    _In_ PVOID clientContext,
    _In_ VHFOPERATIONHANDLE operation,
    _In_opt_ PVOID operationContext,
    _In_ PHID_XFER_PACKET packet)
{
    NTSTATUS status;
    UNREFERENCED_PARAMETER(operationContext);
    status = HandleOutputReport((PDEVICE_CONTEXT)clientContext, packet);
    VhfAsyncOperationComplete(operation, status);
}

VOID
CodexEvtGetFeature(
    _In_ PVOID clientContext,
    _In_ VHFOPERATIONHANDLE operation,
    _In_opt_ PVOID operationContext,
    _In_ PHID_XFER_PACKET packet)
{
    UNREFERENCED_PARAMETER(clientContext);
    UNREFERENCED_PARAMETER(operationContext);
    if (packet->reportId != REPORT_ID || packet->reportBuffer == NULL ||
        packet->reportBufferLen < REPORT_SIZE) {
        VhfAsyncOperationComplete(operation, STATUS_INVALID_BUFFER_SIZE);
        return;
    }
    RtlZeroMemory(packet->reportBuffer, REPORT_SIZE);
    packet->reportBuffer[0] = REPORT_ID;
    VhfAsyncOperationComplete(operation, STATUS_SUCCESS);
}

VOID
CodexEvtSetFeature(
    _In_ PVOID clientContext,
    _In_ VHFOPERATIONHANDLE operation,
    _In_opt_ PVOID operationContext,
    _In_ PHID_XFER_PACKET packet)
{
    UNREFERENCED_PARAMETER(clientContext);
    UNREFERENCED_PARAMETER(operationContext);
    VhfAsyncOperationComplete(
        operation,
        packet->reportId == REPORT_ID ? STATUS_SUCCESS : STATUS_INVALID_PARAMETER);
}

VOID
CodexEvtGetInputReport(
    _In_ PVOID clientContext,
    _In_ VHFOPERATIONHANDLE operation,
    _In_opt_ PVOID operationContext,
    _In_ PHID_XFER_PACKET packet)
{
    CodexEvtGetFeature(clientContext, operation, operationContext, packet);
}

VOID
CodexEvtDeviceCleanup(_In_ WDFOBJECT deviceObject)
{
    PDEVICE_CONTEXT context = DeviceGetContext(deviceObject);
    if (context->VhfHandle != NULL) {
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
    }
}

NTSTATUS
CodexEvtDeviceAdd(
    _In_ WDFDRIVER driver,
    _Inout_ PWDFDEVICE_INIT deviceInit)
{
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_OBJECT_ATTRIBUTES lockAttributes;
    WDFDEVICE device;
    PDEVICE_CONTEXT context;
    VHF_CONFIG config;
    NTSTATUS status;
    UNREFERENCED_PARAMETER(driver);

    WdfDeviceInitSetDeviceType(deviceInit, FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetExclusive(deviceInit, FALSE);
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, DEVICE_CONTEXT);
    attributes.EvtCleanupCallback = CodexEvtDeviceCleanup;
    status = WdfDeviceCreate(&deviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = DeviceGetContext(device);
    context->VhfHandle = NULL;
    context->RpcLength = 0;
    RtlZeroMemory(context->RpcBuffer, sizeof(context->RpcBuffer));

    WDF_OBJECT_ATTRIBUTES_INIT(&lockAttributes);
    lockAttributes.ParentObject = device;
    status = WdfSpinLockCreate(&lockAttributes, &context->RpcLock);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    VHF_CONFIG_INIT(
        &config,
        WdfDeviceWdmGetDeviceObject(device),
        sizeof(g_ReportDescriptor),
        g_ReportDescriptor);
    config.VhfClientContext = context;
    config.VendorID = CODEX_VID;
    config.ProductID = CODEX_PID;
    config.VersionNumber = CODEX_VERSION;
    config.InstanceID = g_InstanceId;
    config.InstanceIDLength = sizeof(g_InstanceId);
    config.HardwareIDs = g_HardwareIds;
    config.HardwareIDsLength = sizeof(g_HardwareIds);
    config.EvtVhfAsyncOperationWriteReport = CodexEvtWriteReport;
    config.EvtVhfAsyncOperationGetFeature = CodexEvtGetFeature;
    config.EvtVhfAsyncOperationSetFeature = CodexEvtSetFeature;
    config.EvtVhfAsyncOperationGetInputReport = CodexEvtGetInputReport;

    status = VhfCreate(&config, &context->VhfHandle);
    if (!NT_SUCCESS(status)) {
        context->VhfHandle = NULL;
        return status;
    }
    status = VhfStart(context->VhfHandle);
    return status;
}

NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT driverObject,
    _In_ PUNICODE_STRING registryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, CodexEvtDeviceAdd);
    return WdfDriverCreate(
        driverObject,
        registryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
}
