/*++

Copyright (C) Microsoft Corporation, All Rights Reserved.

Module Name:

    vhidmini.cpp

Abstract:

    This module contains the implementation of the driver

Environment:

    Windows Driver Framework (WDF)

--*/

#include "vhidmini.h"
#include <strsafe.h>
#include <stdarg.h>

#ifndef _KERNEL_MODE
static VOID
DriverLog(
    _In_z_ _Printf_format_string_ const CHAR* Format,
    ...
    )
{
    CHAR line[2304];
    DWORD written;
    HANDLE file;
    size_t lineLength;
    va_list args;

    va_start(args, Format);
    if (FAILED(StringCbVPrintfA(line, sizeof(line), Format, args))) {
        va_end(args);
        return;
    }
    va_end(args);

    file = CreateFileW(
        L"C:\\ProgramData\\SpaceMouseCodex\\driver.log",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (SUCCEEDED(StringCbLengthA(line, sizeof(line), &lineLength))) {
        WriteFile(file, line, (DWORD)lineLength, &written, NULL);
    }
    CloseHandle(file);
}
#else
#define DriverLog(...) ((void)0)
#endif

//
// This is the default report descriptor for the virtual Hid device returned
// by the mini driver in response to IOCTL_HID_GET_REPORT_DESCRIPTOR.
//
HID_REPORT_DESCRIPTOR G_DefaultReportDescriptor[] = {
    /* Keyboard, report ID 1. */
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01, 0x05, 0x07, 0x19, 0xE0,
    0x29, 0xE7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00,
    0x25, 0xA4, 0x05, 0x07, 0x19, 0x00, 0x29, 0xA4, 0x81, 0x00, 0xC0,

    /* Consumer control, report ID 2. */
    0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x02, 0x75, 0x10, 0x95, 0x01,
    0x15, 0x00, 0x26, 0xFF, 0x07, 0x19, 0x00, 0x2A, 0xFF, 0x07, 0x81, 0x00,
    0xC0,

    /* Relative pointer, report ID 3. */
    0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x85, 0x03, 0x09, 0x01, 0xA1, 0x00,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x05, 0x15, 0x00, 0x25, 0x01, 0x95, 0x05,
    0x75, 0x01, 0x81, 0x02, 0x95, 0x01, 0x75, 0x03, 0x81, 0x01, 0x05, 0x01,
    0x09, 0x30, 0x09, 0x31, 0x15, 0x81, 0x25, 0x7F, 0x95, 0x02, 0x75, 0x08,
    0x81, 0x06, 0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x95, 0x01, 0x75, 0x08,
    0x81, 0x06, 0x05, 0x0C, 0x0A, 0x38, 0x02, 0x15, 0x81, 0x25, 0x7F, 0x95,
    0x01, 0x75, 0x08, 0x81, 0x06, 0xC0, 0xC0,

    /* OpenAI vendor JSON-RPC transport, report ID 6, 63-byte payload. */
    0x06, 0x00, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x06, 0x09, 0x02, 0x15,
    0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0x81, 0x02, 0x09, 0x03,
    0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0x91, 0x02, 0x09,
    0x04, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0xB1, 0x02,
    0xC0,

    /* Bridge-only vendor output collection, report ID 7. */
    0x06, 0x01, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x07, 0x09, 0x02, 0x15,
    0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x3F, 0x91, 0x02, 0xC0,
};

//
// This is the default HID descriptor returned by the mini driver
// in response to IOCTL_HID_GET_DEVICE_DESCRIPTOR. The size
// of report descriptor is currently the size of G_DefaultReportDescriptor.
//

HID_DESCRIPTOR              G_DefaultHidDescriptor = {
    0x09,   // length of HID descriptor
    0x21,   // descriptor type == HID  0x21
    0x0100, // hid spec release
    0x00,   // country code == Not Specified
    0x01,   // number of HID class descriptors
    {                                       //DescriptorList[0]
        0x22,                               //report descriptor type 0x22
        sizeof(G_DefaultReportDescriptor)   //total length of report descriptor
    }
};

NTSTATUS
DriverEntry(
    _In_  PDRIVER_OBJECT    DriverObject,
    _In_  PUNICODE_STRING   RegistryPath
    )
/*++

Routine Description:
    DriverEntry initializes the driver and is the first routine called by the
    system after the driver is loaded. DriverEntry specifies the other entry
    points in the function driver, such as EvtDevice and DriverUnload.

Parameters Description:

    DriverObject - represents the instance of the function driver that is loaded
    into memory. DriverEntry must initialize members of DriverObject before it
    returns to the caller. DriverObject is allocated by the system before the
    driver is loaded, and it is released by the system after the system unloads
    the function driver from memory.

    RegistryPath - represents the driver specific path in the Registry.
    The function driver can use the path to store driver related data between
    reboots. The path does not store hardware instance specific data.

Return Value:

    STATUS_SUCCESS, or another status value for which NT_SUCCESS(status) equals
                    TRUE if successful,

    STATUS_UNSUCCESSFUL, or another status for which NT_SUCCESS(status) equals
                    FALSE otherwise.

--*/
{
    WDF_DRIVER_CONFIG       config;
    NTSTATUS                status;

    KdPrint(("DriverEntry for VHidMini\n"));

#ifdef _KERNEL_MODE
    //
    // Opt-in to using non-executable pool memory on Windows 8 and later.
    // https://msdn.microsoft.com/en-us/library/windows/hardware/hh920402(v=vs.85).aspx
    //
    ExInitializeDriverRuntime(DrvRtPoolNxOptIn);
#endif

    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);

    status = WdfDriverCreate(DriverObject,
                            RegistryPath,
                            WDF_NO_OBJECT_ATTRIBUTES,
                            &config,
                            WDF_NO_HANDLE);
    if (!NT_SUCCESS(status)) {
        KdPrint(("Error: WdfDriverCreate failed 0x%x\n", status));
        return status;
    }

    return status;
}

NTSTATUS
EvtDeviceAdd(
    _In_  WDFDRIVER         Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit
    )
/*++
Routine Description:

    EvtDeviceAdd is called by the framework in response to AddDevice
    call from the PnP manager. We create and initialize a device object to
    represent a new instance of the device.

Arguments:

    Driver - Handle to a framework driver object created in DriverEntry

    DeviceInit - Pointer to a framework-allocated WDFDEVICE_INIT structure.

Return Value:

    NTSTATUS

--*/
{
    NTSTATUS                status;
    WDF_OBJECT_ATTRIBUTES   deviceAttributes;
    WDFDEVICE               device;
    PDEVICE_CONTEXT         deviceContext;
    PHID_DEVICE_ATTRIBUTES  hidAttributes;
    WDF_OBJECT_ATTRIBUTES   lockAttributes;
    UNREFERENCED_PARAMETER  (Driver);

    KdPrint(("Enter EvtDeviceAdd\n"));

    //
    // Mark ourselves as a filter, which also relinquishes power policy ownership
    //
    WdfFdoInitSetFilter(DeviceInit);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
                            &deviceAttributes,
                            DEVICE_CONTEXT);
    status = WdfDeviceCreate(&DeviceInit,
                            &deviceAttributes,
                            &device);
    if (!NT_SUCCESS(status)) {
        KdPrint(("Error: WdfDeviceCreate failed 0x%x\n", status));
        return status;
    }

    deviceContext = GetDeviceContext(device);
    deviceContext->Device       = device;
    deviceContext->ReportHead   = 0;
    deviceContext->ReportTail   = 0;
    deviceContext->ReportCount  = 0;
    deviceContext->RpcLength    = 0;
    RtlZeroMemory(deviceContext->ReportQueue, sizeof(deviceContext->ReportQueue));
    RtlZeroMemory(deviceContext->RpcBuffer, sizeof(deviceContext->RpcBuffer));

    WDF_OBJECT_ATTRIBUTES_INIT(&lockAttributes);
    lockAttributes.ParentObject = device;
    status = WdfWaitLockCreate(&lockAttributes, &deviceContext->ReportLock);
    if (!NT_SUCCESS(status)) {
        KdPrint(("Error: WdfWaitLockCreate failed 0x%x\n", status));
        return status;
    }

    hidAttributes = &deviceContext->HidDeviceAttributes;
    RtlZeroMemory(hidAttributes, sizeof(HID_DEVICE_ATTRIBUTES));
    hidAttributes->Size         = sizeof(HID_DEVICE_ATTRIBUTES);
    hidAttributes->VendorID     = HIDMINI_VID;
    hidAttributes->ProductID    = HIDMINI_PID;
    hidAttributes->VersionNumber = HIDMINI_VERSION;

    status = QueueCreate(device,
                         &deviceContext->DefaultQueue);
    if( !NT_SUCCESS(status) ) {
        return status;
    }

    status = ManualQueueCreate(device,
                               &deviceContext->ManualQueue);
    if( !NT_SUCCESS(status) ) {
        return status;
    }

    //
    // Use default "HID Descriptor" (hardcoded). We will set the
    // wReportLength memeber of HID descriptor when we read the
    // the report descriptor either from registry or the hard-coded
    // one.
    //
    deviceContext->HidDescriptor = G_DefaultHidDescriptor;

    //
    // Check to see if we need to read the Report Descriptor from
    // registry. If the "ReadFromRegistry" flag in the registry is set
    // then we will read the descriptor from registry using routine
    // ReadDescriptorFromRegistry(). Otherwise, we will use the
    // hard-coded default report descriptor.
    //

    status = CheckRegistryForDescriptor(device);
    if (NT_SUCCESS(status)){
        //
        // We need to read read descriptor from registry
        //
        status = ReadDescriptorFromRegistry(device);
        if (!NT_SUCCESS(status)){
            KdPrint(("Failed to read descriptor from registry\n"));
        }
    }

    //
    // We will use hard-coded report descriptor if registry one is not used.
    //
    if (!NT_SUCCESS(status)){
        deviceContext->ReportDescriptor = G_DefaultReportDescriptor;
        KdPrint(("Using Hard-coded Report descriptor\n"));
        status = STATUS_SUCCESS;
    }

    return status;
}

#ifdef _KERNEL_MODE
EVT_WDF_IO_QUEUE_IO_INTERNAL_DEVICE_CONTROL EvtIoDeviceControl;
#else
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL          EvtIoDeviceControl;
#endif

NTSTATUS
QueueCreate(
    _In_  WDFDEVICE         Device,
    _Out_ WDFQUEUE          *Queue
    )
/*++
Routine Description:

    This function creates a default, parallel I/O queue to proces IOCTLs
    from hidclass.sys.

Arguments:

    Device - Handle to a framework device object.

    Queue - Output pointer to a framework I/O queue handle, on success.

Return Value:

    NTSTATUS

--*/
{
    NTSTATUS                status;
    WDF_IO_QUEUE_CONFIG     queueConfig;
    WDF_OBJECT_ATTRIBUTES   queueAttributes;
    WDFQUEUE                queue;
    PQUEUE_CONTEXT          queueContext;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(
                            &queueConfig,
                            WdfIoQueueDispatchSequential);

#ifdef _KERNEL_MODE
    queueConfig.EvtIoInternalDeviceControl  = EvtIoDeviceControl;
#else
    //
    // HIDclass uses INTERNAL_IOCTL which is not supported by UMDF. Therefore
    // the hidumdf.sys changes the IOCTL type to DEVICE_CONTROL for next stack
    // and sends it down
    //
    queueConfig.EvtIoDeviceControl          = EvtIoDeviceControl;
#endif

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
                            &queueAttributes,
                            QUEUE_CONTEXT);

    status = WdfIoQueueCreate(
                            Device,
                            &queueConfig,
                            &queueAttributes,
                            &queue);

    if( !NT_SUCCESS(status) ) {
        KdPrint(("WdfIoQueueCreate failed 0x%x\n",status));
        return status;
    }

    queueContext = GetQueueContext(queue);
    queueContext->Queue         = queue;
    queueContext->DeviceContext = GetDeviceContext(Device);
    queueContext->OutputReport  = 0;

    *Queue = queue;
    return status;
}

VOID
EvtIoDeviceControl(
    _In_  WDFQUEUE          Queue,
    _In_  WDFREQUEST        Request,
    _In_  size_t            OutputBufferLength,
    _In_  size_t            InputBufferLength,
    _In_  ULONG             IoControlCode
    )
/*++
Routine Description:

    This event callback function is called when the driver receives an

    (KMDF) IOCTL_HID_Xxx code when handlng IRP_MJ_INTERNAL_DEVICE_CONTROL
    (UMDF) IOCTL_HID_Xxx, IOCTL_UMDF_HID_Xxx when handling IRP_MJ_DEVICE_CONTROL

Arguments:

    Queue - A handle to the queue object that is associated with the I/O request

    Request - A handle to a framework request object.

    OutputBufferLength - The length, in bytes, of the request's output buffer,
            if an output buffer is available.

    InputBufferLength - The length, in bytes, of the request's input buffer, if
            an input buffer is available.

    IoControlCode - The driver or system defined IOCTL associated with the request

Return Value:

    NTSTATUS

--*/
{
    NTSTATUS                status;
    BOOLEAN                 completeRequest = TRUE;
    WDFDEVICE               device = WdfIoQueueGetDevice(Queue);
    PDEVICE_CONTEXT         deviceContext = NULL;
    PQUEUE_CONTEXT          queueContext = GetQueueContext(Queue);
    UNREFERENCED_PARAMETER  (OutputBufferLength);
    UNREFERENCED_PARAMETER  (InputBufferLength);

    deviceContext = GetDeviceContext(device);

    switch (IoControlCode)
    {
    case IOCTL_HID_GET_DEVICE_DESCRIPTOR:   // METHOD_NEITHER
        //
        // Retrieves the device's HID descriptor.
        //
        _Analysis_assume_(deviceContext->HidDescriptor.bLength != 0);
        status = RequestCopyFromBuffer(Request,
                            &deviceContext->HidDescriptor,
                            deviceContext->HidDescriptor.bLength);
        break;

    case IOCTL_HID_GET_DEVICE_ATTRIBUTES:   // METHOD_NEITHER
        //
        //Retrieves a device's attributes in a HID_DEVICE_ATTRIBUTES structure.
        //
        status = RequestCopyFromBuffer(Request,
                            &queueContext->DeviceContext->HidDeviceAttributes,
                            sizeof(HID_DEVICE_ATTRIBUTES));
        break;

    case IOCTL_HID_GET_REPORT_DESCRIPTOR:   // METHOD_NEITHER
        //
        //Obtains the report descriptor for the HID device.
        //
        status = RequestCopyFromBuffer(Request,
                            deviceContext->ReportDescriptor,
                            deviceContext->HidDescriptor.DescriptorList[0].wReportLength);
        break;

    case IOCTL_HID_READ_REPORT:             // METHOD_NEITHER
        //
        // Returns a report from the device into a class driver-supplied
        // buffer.
        //
        status = ReadReport(queueContext, Request, &completeRequest);
        break;

    case IOCTL_HID_WRITE_REPORT:            // METHOD_NEITHER
        //
        // Transmits a class driver-supplied report to the device.
        //
        status = WriteReport(queueContext, Request);
        break;

#ifdef _KERNEL_MODE

    case IOCTL_HID_GET_FEATURE:             // METHOD_OUT_DIRECT

        status = GetFeature(queueContext, Request);
        break;

    case IOCTL_HID_SET_FEATURE:             // METHOD_IN_DIRECT

        status = SetFeature(queueContext, Request);
        break;

    case IOCTL_HID_GET_INPUT_REPORT:        // METHOD_OUT_DIRECT

        status = GetInputReport(queueContext, Request);
        break;

    case IOCTL_HID_SET_OUTPUT_REPORT:       // METHOD_IN_DIRECT

        status = SetOutputReport(queueContext, Request);
        break;

#else // UMDF specific

    //
    // HID minidriver IOCTL uses HID_XFER_PACKET which contains an embedded pointer.
    //
    //   typedef struct _HID_XFER_PACKET {
    //     PUCHAR reportBuffer;
    //     ULONG  reportBufferLen;
    //     UCHAR  reportId;
    //   } HID_XFER_PACKET, *PHID_XFER_PACKET;
    //
    // UMDF cannot handle embedded pointers when marshalling buffers between processes.
    // Therefore a special driver mshidumdf.sys is introduced to convert such IRPs to
    // new IRPs (with new IOCTL name like IOCTL_UMDF_HID_Xxxx) where:
    //
    //   reportBuffer - passed as one buffer inside the IRP
    //   reportId     - passed as a second buffer inside the IRP
    //
    // The new IRP is then passed to UMDF host and driver for further processing.
    //

    case IOCTL_UMDF_HID_GET_FEATURE:        // METHOD_NEITHER

        status = GetFeature(queueContext, Request);
        break;

    case IOCTL_UMDF_HID_SET_FEATURE:        // METHOD_NEITHER

        status = SetFeature(queueContext, Request);
        break;

    case IOCTL_UMDF_HID_GET_INPUT_REPORT:  // METHOD_NEITHER

        status = GetInputReport(queueContext, Request);
        break;

    case IOCTL_UMDF_HID_SET_OUTPUT_REPORT: // METHOD_NEITHER

        status = SetOutputReport(queueContext, Request);
        break;

#endif // _KERNEL_MODE

    case IOCTL_HID_GET_STRING:                      // METHOD_NEITHER

        status = GetString(Request);
        break;

    case IOCTL_HID_GET_INDEXED_STRING:              // METHOD_OUT_DIRECT

        status = GetIndexedString(Request);
        break;

    case IOCTL_HID_SEND_IDLE_NOTIFICATION_REQUEST:  // METHOD_NEITHER
        //
        // This has the USBSS Idle notification callback. If the lower driver
        // can handle it (e.g. USB stack can handle it) then pass it down
        // otherwise complete it here as not inplemented. For a virtual
        // device, idling is not needed.
        //
        // Not implemented. fall through...
        //
    case IOCTL_HID_ACTIVATE_DEVICE:                 // METHOD_NEITHER
    case IOCTL_HID_DEACTIVATE_DEVICE:               // METHOD_NEITHER
    case IOCTL_GET_PHYSICAL_DESCRIPTOR:             // METHOD_OUT_DIRECT
        //
        // We don't do anything for these IOCTLs but some minidrivers might.
        //
        // Not implemented. fall through...
        //
    default:
        status = STATUS_NOT_IMPLEMENTED;
        break;
    }

    //
    // Complete the request. Information value has already been set by request
    // handlers.
    //
    if (completeRequest) {
        WdfRequestComplete(Request, status);
    }
}

NTSTATUS
RequestCopyFromBuffer(
    _In_  WDFREQUEST        Request,
    _In_  PVOID             SourceBuffer,
    _When_(NumBytesToCopyFrom == 0, __drv_reportError(NumBytesToCopyFrom cannot be zero))
    _In_  size_t            NumBytesToCopyFrom
    )
/*++

Routine Description:

    A helper function to copy specified bytes to the request's output memory

Arguments:

    Request - A handle to a framework request object.

    SourceBuffer - The buffer to copy data from.

    NumBytesToCopyFrom - The length, in bytes, of data to be copied.

Return Value:

    NTSTATUS

--*/
{
    NTSTATUS                status;
    WDFMEMORY               memory;
    size_t                  outputBufferLength;

    status = WdfRequestRetrieveOutputMemory(Request, &memory);
    if( !NT_SUCCESS(status) ) {
        KdPrint(("WdfRequestRetrieveOutputMemory failed 0x%x\n",status));
        return status;
    }

    WdfMemoryGetBuffer(memory, &outputBufferLength);
    if (outputBufferLength < NumBytesToCopyFrom) {
        status = STATUS_INVALID_BUFFER_SIZE;
        KdPrint(("RequestCopyFromBuffer: buffer too small. Size %d, expect %d\n",
                (int)outputBufferLength, (int)NumBytesToCopyFrom));
        return status;
    }

    status = WdfMemoryCopyFromBuffer(memory,
                                    0,
                                    SourceBuffer,
                                    NumBytesToCopyFrom);
    if( !NT_SUCCESS(status) ) {
        KdPrint(("WdfMemoryCopyFromBuffer failed 0x%x\n",status));
        return status;
    }

    WdfRequestSetInformation(Request, NumBytesToCopyFrom);
    return status;
}

NTSTATUS
ReadReport(
    _In_  PQUEUE_CONTEXT    QueueContext,
    _In_  WDFREQUEST        Request,
    _Always_(_Out_)
          BOOLEAN*          CompleteRequest
    )
/*++

Routine Description:

    Handles IOCTL_HID_READ_REPORT for the HID collection. Normally the request
    will be forwarded to a manual queue for further process. In that case, the
    caller should not try to complete the request at this time, as the request
    will later be retrieved back from the manually queue and completed there.
    However, if for some reason the forwarding fails, the caller still need
    to complete the request with proper error code immediately.

Arguments:

    QueueContext - The object context associated with the queue

    Request - Pointer to  Request Packet.

    CompleteRequest - A boolean output value, indicating whether the caller
            should complete the request or not

Return Value:

    NT status code.

--*/
{
    NTSTATUS                status;

    KdPrint(("ReadReport\n"));

    //
    // forward the request to manual queue
    //
    status = WdfRequestForwardToIoQueue(
                            Request,
                            QueueContext->DeviceContext->ManualQueue);
    if( !NT_SUCCESS(status) ) {
        KdPrint(("WdfRequestForwardToIoQueue failed with 0x%x\n", status));
        *CompleteRequest = TRUE;
    }
    else {
        *CompleteRequest = FALSE;
        TryCompleteInputReport(QueueContext->DeviceContext);
    }

    return status;
}

NTSTATUS
WriteReport(
    _In_  PQUEUE_CONTEXT    QueueContext,
    _In_  WDFREQUEST        Request
    )
/*++

Routine Description:

    Handles IOCTL_HID_WRITE_REPORT all the collection.

Arguments:

    QueueContext - The object context associated with the queue

    Request - Pointer to  Request Packet.

Return Value:

    NT status code.

--*/

{
    NTSTATUS                status;
    HID_XFER_PACKET         packet;
    ULONG                   reportSize;
    PHIDMINI_OUTPUT_REPORT  outputReport;
    HIDMINI_INPUT_REPORT    injectedReport;

    KdPrint(("WriteReport\n"));

    status = RequestGetHidXferPacket_ToWriteToDevice(
                            Request,
                            &packet);
    if( !NT_SUCCESS(status) ) {
        return status;
    }

    if (packet.reportId != CONTROL_COLLECTION_REPORT_ID &&
        packet.reportId != INJECTION_COLLECTION_REPORT_ID) {
        //
        // Return error for unknown collection
        //
        status = STATUS_INVALID_PARAMETER;
        KdPrint(("WriteReport: unkown report id %d\n", packet.reportId));
        return status;
    }

    //
    // before touching buffer make sure buffer is big enough.
    //
    reportSize = sizeof(HIDMINI_OUTPUT_REPORT);

    if (packet.reportBufferLen < reportSize) {
        status = STATUS_INVALID_BUFFER_SIZE;
        KdPrint(("WriteReport: invalid input buffer. size %d, expect %d\n",
                            packet.reportBufferLen, reportSize));
        return status;
    }

    outputReport = (PHIDMINI_OUTPUT_REPORT)packet.reportBuffer;

    if (packet.reportId == INJECTION_COLLECTION_REPORT_ID) {
        injectedReport.ReportId = CONTROL_COLLECTION_REPORT_ID;
        RtlCopyMemory(
            injectedReport.Data,
            outputReport->Data,
            sizeof(injectedReport.Data));
        DriverLog(
            "INJECT write channel=%u length=%u\r\n",
            injectedReport.Data[0],
            injectedReport.Data[1]);
        status = EnqueueInputReport(QueueContext->DeviceContext, &injectedReport);
    } else {
        status = HandleOutputReport(QueueContext->DeviceContext, outputReport);
    }
    if (!NT_SUCCESS(status)) {
        return status;
    }

    TryCompleteInputReport(QueueContext->DeviceContext);

    //
    // set status and information
    //
    WdfRequestSetInformation(Request, reportSize);
    return status;
}


HRESULT
GetFeature(
    _In_ PQUEUE_CONTEXT QueueContext,
    _In_ WDFREQUEST Request
    )
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    ULONG reportSize = sizeof(HIDMINI_CONTROL_INFO);
    UNREFERENCED_PARAMETER(QueueContext);

    status = RequestGetHidXferPacket_ToReadFromDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != CONTROL_COLLECTION_REPORT_ID) {
        return STATUS_INVALID_PARAMETER;
    }
    if (packet.reportBufferLen < reportSize) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    RtlZeroMemory(packet.reportBuffer, reportSize);
    packet.reportBuffer[0] = CONTROL_COLLECTION_REPORT_ID;
    WdfRequestSetInformation(Request, reportSize);
    return status;
}

NTSTATUS
SetFeature(
    _In_ PQUEUE_CONTEXT QueueContext,
    _In_ WDFREQUEST Request
    )
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    ULONG reportSize = sizeof(HIDMINI_CONTROL_INFO);
    PHIDMINI_OUTPUT_REPORT outputReport;
    HIDMINI_INPUT_REPORT injectedReport;

    status = RequestGetHidXferPacket_ToWriteToDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != CONTROL_COLLECTION_REPORT_ID &&
        packet.reportId != INJECTION_COLLECTION_REPORT_ID) {
        return STATUS_INVALID_PARAMETER;
    }
    if (packet.reportBufferLen < reportSize) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    if (packet.reportId == INJECTION_COLLECTION_REPORT_ID) {
        outputReport = (PHIDMINI_OUTPUT_REPORT)packet.reportBuffer;
        injectedReport.ReportId = CONTROL_COLLECTION_REPORT_ID;
        RtlCopyMemory(
            injectedReport.Data,
            outputReport->Data,
            sizeof(injectedReport.Data));
        DriverLog(
            "INJECT feature channel=%u length=%u\r\n",
            injectedReport.Data[0],
            injectedReport.Data[1]);
        status = EnqueueInputReport(QueueContext->DeviceContext, &injectedReport);
        if (!NT_SUCCESS(status)) {
            return status;
        }
        TryCompleteInputReport(QueueContext->DeviceContext);
    }

    WdfRequestSetInformation(Request, reportSize);
    return STATUS_SUCCESS;
}

NTSTATUS
GetInputReport(
    _In_ PQUEUE_CONTEXT QueueContext,
    _In_ WDFREQUEST Request
    )
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    ULONG reportSize = sizeof(HIDMINI_INPUT_REPORT);
    UNREFERENCED_PARAMETER(QueueContext);

    status = RequestGetHidXferPacket_ToReadFromDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != CONTROL_COLLECTION_REPORT_ID) {
        return STATUS_INVALID_PARAMETER;
    }
    if (packet.reportBufferLen < reportSize) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    RtlZeroMemory(packet.reportBuffer, reportSize);
    packet.reportBuffer[0] = CONTROL_COLLECTION_REPORT_ID;
    WdfRequestSetInformation(Request, reportSize);
    return status;
}

NTSTATUS
SetOutputReport(
    _In_ PQUEUE_CONTEXT QueueContext,
    _In_ WDFREQUEST Request
    )
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    ULONG reportSize = sizeof(HIDMINI_OUTPUT_REPORT);
    PHIDMINI_OUTPUT_REPORT outputReport;
    HIDMINI_INPUT_REPORT injectedReport;

    status = RequestGetHidXferPacket_ToWriteToDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != CONTROL_COLLECTION_REPORT_ID &&
        packet.reportId != INJECTION_COLLECTION_REPORT_ID) {
        return STATUS_INVALID_PARAMETER;
    }
    if (packet.reportBufferLen < reportSize) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    outputReport = (PHIDMINI_OUTPUT_REPORT)packet.reportBuffer;
    if (packet.reportId == INJECTION_COLLECTION_REPORT_ID) {
        injectedReport.ReportId = CONTROL_COLLECTION_REPORT_ID;
        RtlCopyMemory(
            injectedReport.Data,
            outputReport->Data,
            sizeof(injectedReport.Data));
        DriverLog(
            "INJECT output channel=%u length=%u\r\n",
            injectedReport.Data[0],
            injectedReport.Data[1]);
        status = EnqueueInputReport(QueueContext->DeviceContext, &injectedReport);
    } else {
        status = HandleOutputReport(
            QueueContext->DeviceContext,
            outputReport);
    }
    if (!NT_SUCCESS(status)) {
        return status;
    }

    TryCompleteInputReport(QueueContext->DeviceContext);
    WdfRequestSetInformation(Request, reportSize);
    return status;
}

NTSTATUS
GetStringId(
    _In_  WDFREQUEST        Request,
    _Out_ ULONG            *StringId,
    _Out_ ULONG            *LanguageId
    )
/*++

Routine Description:

    Helper routine to decode IOCTL_HID_GET_INDEXED_STRING and IOCTL_HID_GET_STRING.

Arguments:

    Request - Pointer to Request Packet.

Return Value:

    NT status code.

--*/
{
    NTSTATUS                status;
    ULONG                   inputValue;

#ifdef _KERNEL_MODE

    WDF_REQUEST_PARAMETERS  requestParameters;

    //
    // IOCTL_HID_GET_STRING:                      // METHOD_NEITHER
    // IOCTL_HID_GET_INDEXED_STRING:              // METHOD_OUT_DIRECT
    //
    // The string id (or string index) is passed in Parameters.DeviceIoControl.
    // Type3InputBuffer. However, Parameters.DeviceIoControl.InputBufferLength
    // was not initialized by hidclass.sys, therefore trying to access the
    // buffer with WdfRequestRetrieveInputMemory will fail
    //
    // Another problem with IOCTL_HID_GET_INDEXED_STRING is that METHOD_OUT_DIRECT
    // expects the input buffer to be Irp->AssociatedIrp.SystemBuffer instead of
    // Type3InputBuffer. That will also fail WdfRequestRetrieveInputMemory.
    //
    // The solution to the above two problems is to get Type3InputBuffer directly
    //
    // Also note that instead of the buffer's content, it is the buffer address
    // that was used to store the string id (or index)
    //

    WDF_REQUEST_PARAMETERS_INIT(&requestParameters);
    WdfRequestGetParameters(Request, &requestParameters);

    inputValue = PtrToUlong(
        requestParameters.Parameters.DeviceIoControl.Type3InputBuffer);

    status = STATUS_SUCCESS;

#else

    WDFMEMORY               inputMemory;
    size_t                  inputBufferLength;
    PVOID                   inputBuffer;

    //
    // mshidumdf.sys updates the IRP and passes the string id (or index) through
    // the input buffer correctly based on the IOCTL buffer type
    //

    status = WdfRequestRetrieveInputMemory(Request, &inputMemory);
    if( !NT_SUCCESS(status) ) {
        KdPrint(("WdfRequestRetrieveInputMemory failed 0x%x\n",status));
        return status;
    }
    inputBuffer = WdfMemoryGetBuffer(inputMemory, &inputBufferLength);

    //
    // make sure buffer is big enough.
    //
    if (inputBufferLength < sizeof(ULONG))
    {
        status = STATUS_INVALID_BUFFER_SIZE;
        KdPrint(("GetStringId: invalid input buffer. size %d, expect %d\n",
                            (int)inputBufferLength, (int)sizeof(ULONG)));
        return status;
    }

    inputValue = (*(PULONG)inputBuffer);

#endif

    //
    // The least significant two bytes of the INT value contain the string id.
    //
    *StringId = (inputValue & 0x0ffff);

    //
    // The most significant two bytes of the INT value contain the language
    // ID (for example, a value of 1033 indicates English).
    //
    *LanguageId = (inputValue >> 16);

    return status;
}


NTSTATUS
GetIndexedString(
    _In_  WDFREQUEST        Request
    )
/*++

Routine Description:

    Handles IOCTL_HID_GET_INDEXED_STRING

Arguments:

    Request - Pointer to Request Packet.

Return Value:

    NT status code.

--*/
{
    NTSTATUS                status;
    ULONG                   languageId, stringIndex;

    status = GetStringId(Request, &stringIndex, &languageId);

    // While we don't use the language id, some minidrivers might.
    //
    UNREFERENCED_PARAMETER(languageId);

    if (NT_SUCCESS(status)) {

        if (stringIndex != VHIDMINI_DEVICE_STRING_INDEX)
        {
            status = STATUS_INVALID_PARAMETER;
            KdPrint(("GetString: unkown string index %d\n", stringIndex));
            return status;
        }

        status = RequestCopyFromBuffer(Request, VHIDMINI_DEVICE_STRING, sizeof(VHIDMINI_DEVICE_STRING));
    }
    return status;
}


NTSTATUS
GetString(
    _In_  WDFREQUEST        Request
    )
/*++

Routine Description:

    Handles IOCTL_HID_GET_STRING.

Arguments:

    Request - Pointer to Request Packet.

Return Value:

    NT status code.

--*/
{
    NTSTATUS                status;
    ULONG                   languageId, stringId;
    size_t                  stringSizeCb;
    PWSTR                   string;

    status = GetStringId(Request, &stringId, &languageId);

    // While we don't use the language id, some minidrivers might.
    //
    UNREFERENCED_PARAMETER(languageId);

    if (!NT_SUCCESS(status)) {
        return status;
    }

    switch (stringId){
    case HID_STRING_ID_IMANUFACTURER:
        stringSizeCb = sizeof(VHIDMINI_MANUFACTURER_STRING);
        string = VHIDMINI_MANUFACTURER_STRING;
        break;
    case HID_STRING_ID_IPRODUCT:
        stringSizeCb = sizeof(VHIDMINI_PRODUCT_STRING);
        string = VHIDMINI_PRODUCT_STRING;
        break;
    case HID_STRING_ID_ISERIALNUMBER:
        stringSizeCb = sizeof(VHIDMINI_SERIAL_NUMBER_STRING);
        string = VHIDMINI_SERIAL_NUMBER_STRING;
        break;
    default:
        status = STATUS_INVALID_PARAMETER;
        KdPrint(("GetString: unkown string id %d\n", stringId));
        return status;
    }

    status = RequestCopyFromBuffer(Request, string, stringSizeCb);
    return status;
}


NTSTATUS
ManualQueueCreate(
    _In_ WDFDEVICE Device,
    _Out_ WDFQUEUE *Queue
    )
{
    NTSTATUS status;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDF_OBJECT_ATTRIBUTES queueAttributes;
    WDFQUEUE queue;
    PMANUAL_QUEUE_CONTEXT queueContext;

    WDF_IO_QUEUE_CONFIG_INIT(&queueConfig, WdfIoQueueDispatchManual);
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
        &queueAttributes,
        MANUAL_QUEUE_CONTEXT);

    status = WdfIoQueueCreate(
        Device,
        &queueConfig,
        &queueAttributes,
        &queue);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    queueContext = GetManualQueueContext(queue);
    queueContext->Queue = queue;
    queueContext->DeviceContext = GetDeviceContext(Device);
    *Queue = queue;
    return status;
}

NTSTATUS
FindJsonStringField(
    _In_reads_bytes_(Length) const CHAR* Json,
    _In_ ULONG Length,
    _In_z_ const CHAR* Field,
    _Out_writes_z_(OutputCapacity) CHAR* Output,
    _In_ ULONG OutputCapacity
    )
{
    ULONG i;
    ULONG fieldLength = 0;

    while (Field[fieldLength] != '\0') {
        fieldLength++;
    }

    for (i = 0; i + fieldLength + 2 < Length; i++) {
        ULONG cursor;
        ULONG outputLength = 0;

        if (Json[i] != '"' ||
            !RtlEqualMemory(Json + i + 1, Field, fieldLength) ||
            Json[i + fieldLength + 1] != '"') {
            continue;
        }

        cursor = i + fieldLength + 2;
        while (cursor < Length &&
               (Json[cursor] == ' ' || Json[cursor] == '\t' || Json[cursor] == ':')) {
            cursor++;
        }
        if (cursor >= Length || Json[cursor] != '"') {
            continue;
        }
        cursor++;
        while (cursor < Length && Json[cursor] != '"') {
            if (outputLength + 1 >= OutputCapacity) {
                return STATUS_BUFFER_TOO_SMALL;
            }
            Output[outputLength++] = Json[cursor++];
        }
        if (cursor >= Length) {
            return STATUS_INVALID_PARAMETER;
        }
        Output[outputLength] = '\0';
        return STATUS_SUCCESS;
    }

    return STATUS_NOT_FOUND;
}

NTSTATUS
FindJsonIntegerField(
    _In_reads_bytes_(Length) const CHAR* Json,
    _In_ ULONG Length,
    _In_z_ const CHAR* Field,
    _Out_ LONG* Value
    )
{
    ULONG i;
    ULONG fieldLength = 0;
    LONG depth = 0;
    BOOLEAN inString = FALSE;
    BOOLEAN escaped = FALSE;

    while (Field[fieldLength] != '\0') {
        fieldLength++;
    }

    for (i = 0; i + fieldLength + 2 < Length; i++) {
        ULONG cursor;
        LONG value = 0;
        BOOLEAN negative = FALSE;
        BOOLEAN foundDigit = FALSE;
        CHAR current = Json[i];

        if (inString) {
            if (escaped) {
                escaped = FALSE;
            } else if (current == '\\') {
                escaped = TRUE;
            } else if (current == '"') {
                inString = FALSE;
            }
            continue;
        }

        if (current == '{' || current == '[') {
            depth++;
            continue;
        }
        if (current == '}' || current == ']') {
            depth--;
            continue;
        }
        if (current != '"') {
            continue;
        }

        /* RPC request fields live directly in the root JSON object. */
        if (depth != 1 ||
            !RtlEqualMemory(Json + i + 1, Field, fieldLength) ||
            Json[i + fieldLength + 1] != '"') {
            inString = TRUE;
            continue;
        }

        cursor = i + fieldLength + 2;
        while (cursor < Length && (Json[cursor] == ' ' || Json[cursor] == '\t')) {
            cursor++;
        }
        if (cursor >= Length || Json[cursor] != ':') {
            inString = TRUE;
            continue;
        }
        cursor++;
        while (cursor < Length && (Json[cursor] == ' ' || Json[cursor] == '\t')) {
            cursor++;
        }
        if (cursor < Length && Json[cursor] == '-') {
            negative = TRUE;
            cursor++;
        }
        while (cursor < Length && Json[cursor] >= '0' && Json[cursor] <= '9') {
            foundDigit = TRUE;
            value = (value * 10) + (Json[cursor] - '0');
            cursor++;
        }
        if (foundDigit) {
            *Value = negative ? -value : value;
            return STATUS_SUCCESS;
        }
    }

    return STATUS_NOT_FOUND;
}

BOOLEAN
AsciiEquals(
    _In_z_ const CHAR* Left,
    _In_z_ const CHAR* Right
    )
{
    ULONG i = 0;
    while (Left[i] != '\0' && Right[i] != '\0' && Left[i] == Right[i]) {
        i++;
    }
    return Left[i] == '\0' && Right[i] == '\0';
}

NTSTATUS
SendFramedJson(
    _In_ PDEVICE_CONTEXT DeviceContext,
    _In_reads_bytes_(Length) const CHAR* Json,
    _In_ ULONG Length
    )
{
    ULONG offset = 0;
    NTSTATUS status = STATUS_SUCCESS;

    while (offset < Length) {
        HIDMINI_INPUT_REPORT report;
        ULONG remaining = Length - offset;
        ULONG chunk = remaining > 61 ? 61 : remaining;

        RtlZeroMemory(&report, sizeof(report));
        report.ReportId = CONTROL_COLLECTION_REPORT_ID;
        report.Data[0] = 2;
        report.Data[1] = (UCHAR)chunk;
        RtlCopyMemory(&report.Data[2], Json + offset, chunk);

        status = EnqueueInputReport(DeviceContext, &report);
        if (!NT_SUCCESS(status)) {
            return status;
        }
        TryCompleteInputReport(DeviceContext);
        offset += chunk;
    }

    return status;
}

NTSTATUS
ProcessRpcMessage(
    _In_ PDEVICE_CONTEXT DeviceContext,
    _In_reads_bytes_(Length) const CHAR* Json,
    _In_ ULONG Length
    )
{
    CHAR method[64];
    CHAR response[512];
    LONG id;
    NTSTATUS status;
    ULONG responseLength = 0;

    status = FindJsonStringField(Json, Length, "method", method, sizeof(method));
    if (!NT_SUCCESS(status)) {
        status = FindJsonStringField(Json, Length, "m", method, sizeof(method));
    }
    if (!NT_SUCCESS(status)) {
        return STATUS_SUCCESS;
    }

    status = FindJsonIntegerField(Json, Length, "id", &id);
    if (!NT_SUCCESS(status)) {
        status = FindJsonIntegerField(Json, Length, "i", &id);
    }
    if (!NT_SUCCESS(status) || id < 0) {
        DriverLog("RPC DROP no-id: %.*s\r\n", (int)Length, Json);
        return STATUS_SUCCESS;
    }

    DriverLog("RPC IN method=%s id=%ld bytes=%lu\r\n", method, id, Length);

    if (AsciiEquals(method, "device.status")) {
        status = StringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"version\":\"v1.0\",\"profile_index\":0,\"layer_index\":1,\"battery\":100,\"is_charging\":false}}\r\n",
            id,
            method);
    } else if (AsciiEquals(method, "sys.version")) {
        status = StringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"version\":\"v1.0\"}}\r\n",
            id,
            method);
    } else {
        status = StringCbPrintfA(
            response,
            sizeof(response),
            "{\"id\":%ld,\"method\":\"%s\",\"result\":{\"ok\":1}}\r\n",
            id,
            method);
    }
    if (!NT_SUCCESS(status)) {
        return status;
    }

    while (response[responseLength] != '\0') {
        responseLength++;
    }
    DriverLog("RPC OUT method=%s id=%ld bytes=%lu\r\n", method, id, responseLength);
    return SendFramedJson(DeviceContext, response, responseLength);
}

NTSTATUS
HandleOutputReport(
    _In_ PDEVICE_CONTEXT DeviceContext,
    _In_ PHIDMINI_OUTPUT_REPORT Report
    )
{
    ULONG chunkLength;
    CHAR method[64];
    NTSTATUS status;

    if (Report->ReportId != CONTROL_COLLECTION_REPORT_ID || Report->Data[0] != 2) {
        return STATUS_INVALID_PARAMETER;
    }
    chunkLength = Report->Data[1];
    if (chunkLength > 61) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    status = FindJsonStringField(
        (const CHAR*)&Report->Data[2],
        chunkLength,
        "m",
        method,
        sizeof(method));
    if (NT_SUCCESS(status) &&
        (AsciiEquals(method, "v.oai.hid") || AsciiEquals(method, "v.oai.rad"))) {
        DriverLog("NOTIFY OUT method=%s bytes=%lu: %.*s\r\n",
            method,
            chunkLength,
            (int)chunkLength,
            &Report->Data[2]);
        status = EnqueueInputReport(DeviceContext, (PHIDMINI_INPUT_REPORT)Report);
        if (NT_SUCCESS(status)) {
            TryCompleteInputReport(DeviceContext);
        }
        return status;
    }

    if (DeviceContext->RpcLength + chunkLength > sizeof(DeviceContext->RpcBuffer)) {
        DeviceContext->RpcLength = 0;
        return STATUS_BUFFER_OVERFLOW;
    }

    RtlCopyMemory(
        DeviceContext->RpcBuffer + DeviceContext->RpcLength,
        &Report->Data[2],
        chunkLength);
    DeviceContext->RpcLength += chunkLength;

    /*
     * Work Louder's HID transport sends JSON without a trailing newline.
     * A packet shorter than the 61-byte payload capacity marks the final
     * chunk.  Keep accepting CR/LF terminated messages for compatibility
     * with serial-style senders and older test tools.
     */
    if (DeviceContext->RpcLength > 0 &&
        (chunkLength < 61 ||
         DeviceContext->RpcBuffer[DeviceContext->RpcLength - 1] == '\n' ||
         DeviceContext->RpcBuffer[DeviceContext->RpcLength - 1] == '\r')) {
        status = ProcessRpcMessage(
            DeviceContext,
            DeviceContext->RpcBuffer,
            DeviceContext->RpcLength);
        DeviceContext->RpcLength = 0;
        RtlZeroMemory(DeviceContext->RpcBuffer, sizeof(DeviceContext->RpcBuffer));
        return status;
    }

    return STATUS_SUCCESS;
}

NTSTATUS
EnqueueInputReport(
    _In_ PDEVICE_CONTEXT DeviceContext,
    _In_ PHIDMINI_INPUT_REPORT Report
    )
{
    ULONG next;

    if (Report->ReportId != CONTROL_COLLECTION_REPORT_ID) {
        return STATUS_INVALID_PARAMETER;
    }

    WdfWaitLockAcquire(DeviceContext->ReportLock, NULL);

    if (DeviceContext->ReportCount == CODEX_MICRO_QUEUE_CAPACITY) {
        DeviceContext->ReportHead =
            (DeviceContext->ReportHead + 1) % CODEX_MICRO_QUEUE_CAPACITY;
        DeviceContext->ReportCount--;
    }

    RtlCopyMemory(
        &DeviceContext->ReportQueue[DeviceContext->ReportTail],
        Report,
        sizeof(HIDMINI_INPUT_REPORT));

    next = (DeviceContext->ReportTail + 1) % CODEX_MICRO_QUEUE_CAPACITY;
    DeviceContext->ReportTail = next;
    DeviceContext->ReportCount++;

    WdfWaitLockRelease(DeviceContext->ReportLock);
    return STATUS_SUCCESS;
}

VOID
TryCompleteInputReport(
    _In_ PDEVICE_CONTEXT DeviceContext
    )
{
    NTSTATUS status;
    WDFREQUEST request = NULL;
    HIDMINI_INPUT_REPORT report;
    BOOLEAN haveReport = FALSE;

    WdfWaitLockAcquire(DeviceContext->ReportLock, NULL);

    if (DeviceContext->ReportCount > 0) {
        status = WdfIoQueueRetrieveNextRequest(
            DeviceContext->ManualQueue,
            &request);

        if (NT_SUCCESS(status)) {
            RtlCopyMemory(
                &report,
                &DeviceContext->ReportQueue[DeviceContext->ReportHead],
                sizeof(report));
            DeviceContext->ReportHead =
                (DeviceContext->ReportHead + 1) % CODEX_MICRO_QUEUE_CAPACITY;
            DeviceContext->ReportCount--;
            haveReport = TRUE;
        }
    }

    WdfWaitLockRelease(DeviceContext->ReportLock);

    if (haveReport) {
        DriverLog(
            "INPUT complete report=%u channel=%u length=%u\r\n",
            report.ReportId,
            report.Data[0],
            report.Data[1]);
        status = RequestCopyFromBuffer(
            request,
            &report,
            sizeof(report));
        WdfRequestComplete(request, status);
    }
}

NTSTATUS
CheckRegistryForDescriptor(
        WDFDEVICE Device
        )
/*++

Routine Description:

    Read "ReadFromRegistry" key value from device parameters in the registry.

Arguments:

    device - pointer to a device object.

Return Value:

    NT status code.

--*/

{
    WDFKEY          hKey = NULL;
    NTSTATUS        status;
    UNICODE_STRING  valueName;
    ULONG           value;

    status = WdfDeviceOpenRegistryKey(Device,
                                  PLUGPLAY_REGKEY_DEVICE,
                                  KEY_READ,
                                  WDF_NO_OBJECT_ATTRIBUTES,
                                  &hKey);
    if (NT_SUCCESS(status)) {

        RtlInitUnicodeString(&valueName, L"ReadFromRegistry");

        status = WdfRegistryQueryULong (hKey,
                                  &valueName,
                                  &value);

        if (NT_SUCCESS (status)) {
            if (value == 0) {
                status = STATUS_UNSUCCESSFUL;
            }
        }

        WdfRegistryClose(hKey);
    }

    return status;
}

NTSTATUS
ReadDescriptorFromRegistry(
        WDFDEVICE Device
        )
/*++

Routine Description:

    Read HID report descriptor from registry

Arguments:

    device - pointer to a device object.

Return Value:

    NT status code.

--*/
{
    WDFKEY          hKey = NULL;
    NTSTATUS        status;
    UNICODE_STRING  valueName;
    WDFMEMORY       memory;
    size_t          bufferSize;
    PVOID           reportDescriptor;
    PDEVICE_CONTEXT deviceContext;
    WDF_OBJECT_ATTRIBUTES   attributes;

    deviceContext = GetDeviceContext(Device);

    status = WdfDeviceOpenRegistryKey(Device,
                                  PLUGPLAY_REGKEY_DEVICE,
                                  KEY_READ,
                                  WDF_NO_OBJECT_ATTRIBUTES,
                                  &hKey);

    if (NT_SUCCESS(status)) {

        RtlInitUnicodeString(&valueName, L"MyReportDescriptor");

        WDF_OBJECT_ATTRIBUTES_INIT(&attributes);
        attributes.ParentObject = Device;

        status = WdfRegistryQueryMemory (hKey,
                                  &valueName,
                                  NonPagedPool,
                                  &attributes,
                                  &memory,
                                  NULL);

        if (NT_SUCCESS (status)) {

            reportDescriptor = WdfMemoryGetBuffer(memory, &bufferSize);

            KdPrint(("No. of report descriptor bytes copied: %d\n", (INT) bufferSize));

            //
            // Store the registry report descriptor in the device extension
            //
            deviceContext->ReadReportDescFromRegistry = TRUE;
            deviceContext->ReportDescriptor = reportDescriptor;
            deviceContext->HidDescriptor.DescriptorList[0].wReportLength = (USHORT)bufferSize;
        }

        WdfRegistryClose(hKey);
    }

    return status;
}
