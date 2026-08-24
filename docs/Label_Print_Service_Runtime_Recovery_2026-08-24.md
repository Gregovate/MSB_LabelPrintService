# Label Print Service Runtime Recovery — 2026-08-24

| Document Control | Value |
|---|---|
| Document Type | Engineering Recovery / Runtime Baseline |
| System | MSB Label Print Service |
| Status | CURRENT RECOVERY CHECKPOINT |
| Owner | MSB Database Administrator |
| Last Reviewed | 2026-08-24 |
| Branch | `agent/label-print-service-engineering-recovery` |

## Purpose

This document supersedes the 2026-08-22 runtime-recovery checkpoint for current PRINT-SERVER startup/recovery facts. The 2026-08-22 document remains useful historical evidence and should not be deleted.

The major recovery objective completed on 2026-08-24 was to reconstruct the actual post-reboot startup path, prove whether an interactive Windows login was technically required, add a safe remote-administration path, and correct the missing unattended startup mechanism without changing `label_poll_service_v3.py`.

## Production Host

Verified directly on the dedicated Beelink Windows host:

```text
Hostname: PRINT-SERVER
IPv4: 192.168.5.56
Windows account: PRINT-SERVER\Print Service
Production working directory: C:\MSB_LabelService
Production Python: C:\Program Files\Python\python.exe
Production service script: C:\MSB_LabelService\label_poll_service_v3.py
Service version: 3.4
```

The prior documentation/reference to a Windows account named `printserver` was inaccurate for the actual interactive/runtime account. The verified account is `PRINT-SERVER\Print Service`.

Credential material remains protected and must not be committed.

## Reconstructed Original Startup Method

The desktop startup icon resolves to:

```text
C:\start_label_service.bat
```

Verified contents:

```bat
@echo off
color 1E
title MSB LABEL SERVICE - DO NOT CLOSE
cd /d C:\MSB_LabelService
"C:\Program Files\Python\python.exe" label_poll_service_v3.py
pause
```

This established the original production behavior:

```text
Windows reboot/update
    -> Windows sign-in screen
    -> user logs into PRINT-SERVER\Print Service
    -> user manually starts the desktop launcher
    -> batch file starts Python v3.4
    -> blue/yellow console remains open
```

The Label Print Service was not previously configured as a Windows service, scheduled task, Startup-folder item, or Run-registry entry.

## Existing Startup Mechanism Search

Direct inspection found no Label Print Service autostart mechanism in:

- Task Scheduler;
- all-users Startup folder;
- `Print Service` user Startup folder;
- HKLM Run registry key;
- HKCU Run registry key.

The post-reboot reliability problem was therefore a missing unattended startup mechanism, not a failure of an existing autostart configuration.

## OpenSSH Recovery Path

Microsoft OpenSSH Server was installed on `PRINT-SERVER` and configured for automatic startup.

Verified:

```text
OpenSSH Server capability: Installed
sshd: Running / Automatic
OpenSSH-Server-In-TCP: Enabled / Inbound / Allow
TCP 22: listening on 0.0.0.0 and ::
```

The machine was rebooted and deliberately left at the Windows sign-in screen. OpenSSH returned automatically and accepted a remote login as `PRINT-SERVER\Print Service` before any desktop login.

This establishes SSH as a valid post-reboot administration path.

## Pre-Login Windows / Printer State

While the machine remained at the Windows sign-in screen:

```text
explorer.exe: not running
python.exe: not running before Label Service start
Windows Spooler: Running / Automatic
Brother PT-P950NW queue: Normal
Brother printer port: 192.168.5.12_1
```

The printer/spooler infrastructure returns at boot independently of an interactive desktop login.

## Headless Service Test

The existing production command was started from SSH while no Windows desktop was logged in:

```cmd
cd /d C:\MSB_LabelService
"C:\Program Files\Python\python.exe" label_poll_service_v3.py
```

The v3.4 startup health check passed and connected to PostgreSQL as `printservice`. The service entered its normal 15-second polling loop.

A real Container label request then physically printed successfully through the Brother PT-P950NW while the machine remained at the sign-in screen.

This proved that an interactive Windows desktop session is not required for:

- Python v3.4;
- protected configuration loading;
- PostgreSQL access;
- actor resolution;
- Brother b-PAC submission;
- Windows spooler operation;
- physical PT-P950NW printing.

## Unattended Startup Change

A Windows Scheduled Task named:

```text
MSB Label Service
```

was created to launch the existing production service without changing service code.

Verified task principal:

```text
UserId    : Print Service
LogonType : Password
RunLevel  : Highest
```

The task is configured to run whether the user is logged on or not.

Production action:

```text
Program/script: C:\Program Files\Python\python.exe
Arguments:      C:\MSB_LabelService\label_poll_service_v3.py
Start in:       C:\MSB_LabelService
```

The startup trigger uses a one-minute delay.

The existing `C:\start_label_service.bat` remains as an interactive fallback and is not the Scheduled Task action.

## Task-Scheduler Setup Findings

Two setup errors were identified and corrected during testing.

### `2147942402` / `0x80070002`

The executable path had been split incorrectly:

```text
Execute   : C:\Program
Arguments : Files\Python\python.exe C:\MSB_LabelService\label_poll_service_v3.py
```

Result: file not found.

### `2147942667` / `0x8007010B`

The working directory contained literal quotation marks:

```text
WorkingDirectory : "C:\MSB_LabelService"
```

Result: directory name invalid.

Correct working directory:

```text
C:\MSB_LabelService
```

with no quotes in the Task Scheduler **Start in** field.

After correction, the task reported:

```text
State: Running
LastTaskResult: 267009
```

`267009` / `0x41301` indicates the long-running scheduled task is currently running.

The resulting process was verified as:

```text
ExecutablePath : C:\Program Files\Python\python.exe
CommandLine    : "C:\Program Files\Python\python.exe" "C:\MSB_LabelService\label_poll_service_v3.py"
```

## Scheduled-Task Physical Print Test

With v3.4 running under Task Scheduler rather than an SSH-attached console, a real Display label request physically printed successfully.

This proved the Scheduled Task execution context can run the complete production chain:

```text
Task Scheduler
    -> Python v3.4
    -> PostgreSQL
    -> Brother b-PAC
    -> Windows spooler
    -> Brother PT-P950NW
    -> physical label
```

## Final Unattended Reboot Acceptance — PASSED

The final production acceptance test passed on 2026-08-24:

1. `PRINT-SERVER` was rebooted.
2. No user logged into Windows to start the Label Print Service.
3. OpenSSH returned automatically.
4. The `MSB Label Service` Scheduled Task started v3.4 automatically after reboot.
5. The Label Print Service resumed normal operation.
6. A real label request was submitted after reboot.
7. The physical label printed successfully.

The known manual-restart weakness is therefore resolved by host/runtime configuration without modifying the Label Print Service application code.

## Current Accepted Runtime Behavior

```text
Windows Update / reboot
    -> Windows reaches normal boot state
    -> Spooler returns automatically
    -> OpenSSH returns automatically
    -> MSB Label Service Scheduled Task starts automatically
    -> Python v3.4 performs startup health check
    -> PostgreSQL polling resumes
    -> b-PAC / spooler / Brother PT-P950NW printing remains operational
```

No interactive Windows login is required for normal production recovery after reboot.

## Current Runbook

The authoritative admin/runtime procedure is now:

[Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md)

The March operator guide still contains historical language requiring the blue console window to remain open. That instruction no longer describes normal production startup and must be reconciled separately rather than treated as current authority.

## Remaining Recovery Work

The startup/reboot problem is resolved, but engineering recovery is not fully complete. Remaining direct-host inventory includes:

- exact Beelink hardware model;
- Brother b-PAC installed version/location on PRINT-SERVER;
- complete Brother driver details beyond the verified queue/port;
- Windows Update policy/history and controlled maintenance policy;
- current machine backup/rebuild/recovery mechanism;
- reconciliation of stale March architecture/operator/TODO documentation;
- reciprocal handoff updates to related MSB repositories where appropriate.

Do not redesign the working service while finishing this inventory.

## Related Documents

- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md)
- [2026-08-22 Runtime Recovery Checkpoint](Label_Print_Service_Runtime_Recovery_2026-08-22.md)
- [Repository README](../readme.md)
- [Label Print Service Engineering Rules](../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)

## Revision History

| Date | Change |
|---|---|
| 2026-08-24 | Reconstructed actual manual startup, enabled and reboot-tested OpenSSH, proved headless b-PAC printing, created and validated the `MSB Label Service` Scheduled Task, and passed unattended reboot plus physical-print acceptance. |
