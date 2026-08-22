# Label Print Service Runtime Recovery — 2026-08-22

| Document Control | Value |
|---|---|
| Document Type | Engineering Recovery / Runtime Baseline |
| System | MSB Label Print Service |
| Status | CURRENT RECOVERY CHECKPOINT |
| Owner | MSB Database Administrator |
| Last Reviewed | 2026-08-22 |
| Branch | `agent/label-print-service-engineering-recovery` |

## Purpose

This document records the verified Label Print Service source/runtime facts recovered on 2026-08-22 before any service redesign or deployment change.

It distinguishes facts verified from Git from facts observed from the Windows workstation session, and it deliberately preserves unresolved host/startup questions instead of guessing.

## Source-Control Baseline

The office-PC changes were pushed to `MSB_LabelPrintService/main` before this recovery branch was created.

Verified source baseline:

```text
Repository: Gregovate/MSB_LabelPrintService
main HEAD: 2ec15fcf9fd39230dfb4aba32721e72e8697b0b4
Recovery branch: agent/label-print-service-engineering-recovery
Current service file: label_poll_service_v3.py
SERVICE_VERSION: 3.4
SHA-256: DFE48D51D4213313F47738B09964BCDFB4788A8B83D5D4CB6130443E7EA3C1BD
```

The v3.4 source contains later engineering changes that are not reflected completely in the March documentation, including:

- v3.2 requester/actor attribution;
- v3.3 failed-batch persistence and repeated-print-storm prevention;
- v3.4 rotating main-service logging;
- explicit pre-print batch commit logging;
- spooler recovery utilities in the repository.

No service-code change has been made as part of this recovery work.

## Working-Tree / Filesystem Observation

The recovery commands were run from a PowerShell session whose current directory was:

```text
\\print-server\MSB_LabelService
```

Git reported:

```text
Repo root: //print-server/MSB_LabelService
branch: main
HEAD: 2ec15fcf9fd39230dfb4aba32721e72e8697b0b4
status: main...origin/main
```

This verifies that the current Git working tree is accessible through the `print-server` SMB/UNC name.

It does **not** by itself prove that `print-server` is a separate Windows host. The PowerShell session itself reported the local computer name `MSB-Office-PC`. The `print-server` name may therefore represent another host, an SMB alias, or another naming arrangement. That relationship remains to be verified.

## Windows Workstation Observed During Recovery

The PowerShell session reported:

```text
Computer name: MSB-Office-PC
User: msb-office-pc\greg
OS: Microsoft Windows 11 Pro
Version: 10.0.26200
Build: 26200
Architecture: 64-bit
Hardware manufacturer: Micro-Star International Co., Ltd.
Model: MS-7D43
```

These are verified facts for the machine on which the recovery PowerShell commands were executed.

Do not yet relabel `MSB-Office-PC` as the definitive Label Print Service host until the `print-server` name and service execution host are reconciled.

## Python Observed on MSB-Office-PC

The default `python` command resolved to:

```text
Python 3.13.7
C:\Users\Greg\AppData\Local\Programs\Python\Python313\python.exe
```

No running `label_poll_service_v3.py` process was found on `MSB-Office-PC` during the 2026-08-22 inspection.

The only Python processes shown were LOR operator-runner processes from the Production Database project.

This means one of the following remains possible and must be verified rather than assumed:

- the Label Print Service was simply stopped at the time of inspection;
- it normally runs manually on `MSB-Office-PC` but was not active;
- it normally runs on another machine that accesses the same `\\print-server\MSB_LabelService` working tree;
- `print-server` is another name/alias for `MSB-Office-PC` and the service is currently stopped.

## Startup / Automatic-Run Observation

The inspection of the **local** `MSB-Office-PC` user/public desktop did not find a shortcut whose name matched `Label` or `Print` that launches the Label Print Service.

The inspection also found no Label Print Service entry in normal Windows startup commands or scheduled tasks. Only standard Microsoft printing tasks were listed.

Therefore the March operator-guide statement that a **Start Label Service** desktop shortcut exists must be treated as **unverified/currently not found on the inspected local desktop**.

The repository root currently contains `KillSpooler.lnk`, but no Git-indexed `Start Label Service` launcher was found during repository search.

Do not modify the operator guide until the actual launcher/start method is identified.

## Protected Configuration

A live configuration file exists at the repository/share root:

```text
\\print-server\MSB_LabelService\config.local.ini
```

Observed metadata:

```text
size: 1050 bytes
last modified: 2026-03-27 17:08:38 local time
```

The contents were deliberately not displayed because the file contains protected runtime configuration.

`config.local.ini` must remain outside Git.

## Brother / b-PAC Software Observed on MSB-Office-PC

Installed Brother software observed on the inspected Windows machine includes:

```text
Brother b-PAC3 SDK (64bit) 3.4.0150
Brother Printer Driver
Brother IPPoverUSB Driver
Brother Printer Setting Tool 1.6.0132
Brother P-touch Editor 6.9.00
Brother P-touch Editor 5.4
Brother P-touch Address Book 1.4
Brother P-touch Update Software
```

Verified b-PAC install location:

```text
C:\Program Files\Brother bPAC3 SDK\
```

The duplicate b-PAC uninstall entry observed in Windows inventory is recorded only as an observed software-inventory condition; no cleanup is authorized or needed for this recovery.

## Brother PT-P950NW Queue Observed on MSB-Office-PC

The Windows printer queue exists and reported normal status:

```text
Name: Brother PT-P950NW
Driver: Brother PT-P950NW
Port: IP_192.168.5.12
Status: Normal
Shared: False
```

The printer port is configured as:

```text
PrinterHostAddress: 192.168.5.12
PortNumber: 515
Protocol: LPR
```

This verifies that `MSB-Office-PC` currently has the correct Brother P950NW Windows queue and network path configured.

It does not yet prove that the Label Print Service currently executes on this same host.

## Current Brother Templates

The shared/runtime tree contains these current `.lbx` templates:

```text
QR_container_horizontal.lbx
  size: 2284 bytes
  modified: 2026-03-21 10:44:11

QR_container_vertical.lbx
  size: 2277 bytes
  modified: 2026-03-21 10:43:28

QR_display_labels_2_line.lbx
  size: 2490 bytes
  modified: 2026-03-21 10:30:57
```

These filenames match the current non-secret configuration example and v3.4 source expectations.

Do not change template object names or template files during engineering recovery.

## Logs / Runtime Evidence

The shared `logs/` directory contains substantial production history.

Observed current rotation state included:

```text
label_service.log       197971 bytes   modified 2026-08-11 22:42:52
label_service.log.1     5242831 bytes  modified 2026-08-11 18:54:20
label_service.log.2     5242807 bytes  modified 2026-07-31 21:24:18
...
label_service.log.10    5242869 bytes  modified 2026-05-10 13:55:38
```

This is consistent with the v3.4 rotating-log implementation and proves that the shared runtime tree was actively used well after the March initial build.

The service source logs its startup identity including the hostname. Therefore the existing logs are the best next evidence source for identifying the actual execution host without changing production.

The `state/` directory was empty at the time of inspection.

## Spooler-Recovery Artifacts

The office-PC push added/currently includes:

```text
KillSpooler.lnk
killspooler.bat
killspooler.ps1
```

The batch/PowerShell scripts stop the Windows Spooler, delete queued spool files, and restart the service.

These are **destructive recovery utilities** because queued jobs are discarded.

They must not be used as normal service-start or troubleshooting steps without first reconciling physical-print and PostgreSQL batch/request state.

## Current Architecture Evidence

The following production path is supported by current source plus the recovered runtime evidence:

```text
Production Database / Directus
    -> PostgreSQL label request and batch state
        -> label_poll_service_v3.py (v3.4)
            -> Brother b-PAC3 SDK
                -> Windows Brother PT-P950NW queue
                    -> LPR 192.168.5.12:515
                        -> Brother PT-P950NW
```

The exact Windows host that executes `label_poll_service_v3.py`, and the exact supported startup method, remain the two main runtime facts not yet closed.

## Documentation Drift Confirmed

The March documentation remains useful engineering evidence but is not fully current.

Confirmed drift includes:

- root README previously referenced v2 even though current source is v3.4;
- `How_Label_Service_Works.md` describes the service generically as v3.x and predates v3.3/v3.4 details;
- the March TODO still describes requester attribution as future work even though v3.2 implemented it;
- the operator guide describes a `Start Label Service` desktop shortcut that was not found on the inspected local desktop;
- the operator guide describes a dedicated print-server machine, but the current relationship between `MSB-Office-PC` and the `print-server` UNC name is still unresolved;
- machine rebuild/backup and current startup/restart authority are not yet adequately documented.

Do not delete the March documents. Reconcile or archive/supersede them only after the current runtime is established.

## Exact Next Recovery Step

Use read-only evidence to identify the `print-server` name and service execution host.

Required questions:

1. Does `print-server` resolve to an IP address assigned to `MSB-Office-PC`, or to another host?
2. What hostname is recorded in recent v3.4 `MSB Label Service ... started` log entries?
3. If the service is manually started, where is the actual current launcher and what command does it execute?

After those facts are known, update this document and the repository README before editing March operator/architecture documentation or changing service behavior.

## Related Documents

- [Repository engineering handoff](../readme.md)
- [How the Label Service Works](How_Label_Service_Works.md)
- [Print Server Operator Guide](Operator_Label_Printing.md)
- [Label Service TODO / historical limitations](TODO_Label_Service.md)
- [Label Print Service Engineering Rules](../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
