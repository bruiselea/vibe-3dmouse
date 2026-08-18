#include <windows.h>
#include <swdevice.h>
#include <cfgmgr32.h>
#include <stdio.h>

#pragma comment(lib, "Swdevice.lib")

struct CREATE_STATE {
    HANDLE Event;
    HRESULT Result;
    WCHAR InstanceId[MAX_DEVICE_ID_LEN];
};

static VOID WINAPI
CreatedCallback(
    HSWDEVICE,
    HRESULT createResult,
    PVOID context,
    PCWSTR deviceInstanceId)
{
    auto state = static_cast<CREATE_STATE*>(context);
    state->Result = createResult;
    if (deviceInstanceId != nullptr) {
        wcsncpy_s(state->InstanceId, deviceInstanceId, _TRUNCATE);
    }
    SetEvent(state->Event);
}

int wmain()
{
    static const WCHAR hardwareIds[] = L"root\\CodexMicroHid\0\0";
    FILETIME now{};
    WCHAR softwareInstanceId[96]{};
    GetSystemTimeAsFileTime(&now);
    swprintf_s(
        softwareInstanceId,
        L"SPACEMOUSE_CODEX_%08lX%08lX_%08lX",
        now.dwHighDateTime,
        now.dwLowDateTime,
        GetCurrentProcessId());
    SW_DEVICE_CREATE_INFO info{};
    info.cbSize = sizeof(info);
    // A removed SWD ID can remain tombstoned until reboot. A unique instance
    // makes uninstall -> immediate reinstall reliable while the stable prefix
    // still lets the uninstaller identify only devices owned by this app.
    info.pszInstanceId = softwareInstanceId;
    info.pszzHardwareIds = hardwareIds;
    info.CapabilityFlags = SWDeviceCapabilitiesSilentInstall;
    info.pszDeviceDescription = L"Codex Micro SpaceMouse Bridge";
    info.pszDeviceLocation = L"Software Device";

    CREATE_STATE state{};
    state.Event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    state.Result = E_PENDING;
    if (state.Event == nullptr) {
        fwprintf(stderr, L"CreateEvent failed: %lu\n", GetLastError());
        return 1;
    }

    HSWDEVICE device = nullptr;
    HRESULT result = SwDeviceCreate(
        L"VID_303A&PID_8360",
        L"HTREE\\ROOT\\0",
        &info,
        0,
        nullptr,
        CreatedCallback,
        &state,
        &device);
    if (FAILED(result)) {
        fwprintf(stderr, L"SwDeviceCreate failed: 0x%08X\n", result);
        CloseHandle(state.Event);
        return 2;
    }

    DWORD wait = WaitForSingleObject(state.Event, 15000);
    if (wait != WAIT_OBJECT_0) {
        fwprintf(stderr, L"Software device enumeration timed out: %lu\n", wait);
        SwDeviceClose(device);
        CloseHandle(state.Event);
        return 3;
    }
    if (FAILED(state.Result)) {
        fwprintf(stderr, L"Software device creation failed: 0x%08X\n", state.Result);
        SwDeviceClose(device);
        CloseHandle(state.Event);
        return 4;
    }

    result = SwDeviceSetLifetime(device, SWDeviceLifetimeParentPresent);
    if (FAILED(result)) {
        fwprintf(stderr, L"SwDeviceSetLifetime failed: 0x%08X\n", result);
        SwDeviceClose(device);
        CloseHandle(state.Event);
        return 5;
    }

    wprintf(L"%s\n", state.InstanceId);
    SwDeviceClose(device);
    CloseHandle(state.Event);
    return 0;
}
