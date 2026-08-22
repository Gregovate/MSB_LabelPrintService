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

The production runtime is a **dedicated Beelink Windows machine**. `MSB-Office-PC` is an administration/development workstation and is not the Label Print Service host.

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

The v3.4 source includes:

- v3.2 requester/actor attribution;
- v3.3 failed-batch persistence and repeated-print-storm prevention;
- v3.4 rotating main-service logging;
- explicit pre-print batch commit logging;
- spooler recovery utilities.

No service-code change has been made during this recovery work.

## Production Host Boundary

The Label Print Service production host is a **dedicated Beelink Windows machine** whose service-recorded Windows hostname is:

```text
PRINT-SERVER
```

Name resolution from `MSB-Office-PC` on 2026-08-22 established:

```text
print-server.localdomain -> 192.168.5.56
```

The production working tree is exposed to the office PC through:

```text
\\print-server\MSB_LabelService
```

SMB connectivity to `PRINT-SERVER` was verified on TCP 445. WinRM / PowerShell Remoting was not enabled: TCP 5985 and 5986 were closed. No remote-management configuration was changed as part of reconnaissance.

The 2026-08-22 reconnaissance commands were initially run from `MSB-Office-PC` while its PowerShell current directory pointed at the UNC share. As a result, the Windows OS, Python installation, local desktop shortcuts, local scheduled tasks, Brother software inventory, and local Windows printer queues returned by that initial command set describe **MSB-Office-PC**, not `PRINT-SERVER`.

Those office-PC observations must not be promoted as print-server runtime facts.

The UNC/Git results remain valid: they verify that the service working tree exposed through `\\print-server\MSB_LabelService` was on `main`, clean against `origin/main`, and at commit `2ec15fcf9fd39230dfb4aba32721e72e8697b0b4` when inspected.

## Runtime Account Boundary

The dedicated Beelink has a Windows user account named:

```text
printserver
```

The account is password-protected. The password and other credential material are **not documentation data and must not be committed to Git**.

The exact role of this account in interactive login, startup, scheduled execution, printer profile ownership, and service recovery still requires direct verification on `PRINT-SERVER`.

## Production Reliability Issue — Windows Update

Automatic Windows Updates are currently enabled on the dedicated Beelink print-server machine.

Operational experience has established that after some Microsoft-pushed updates, the Beelink does not restart cleanly or return the Label Print Service to its normal operational state without intervention.

Treat this as a **production restart/recovery reliability issue**, not a crash condition.

Do not solve it during documentation recovery by blindly disabling Windows Update. The production host needs a deliberate update/reboot policy that preserves security updates while preventing uncontrolled update timing and ensuring the Label Print Service returns to a known-good state after reboot.

The final print-server recovery/runbook must therefore document:

- current Windows Update configuration;
- whether restarts are automatic;
- how the Label Print Service starts after reboot;
- how to verify PostgreSQL connectivity, b-PAC, spooler, printer queue, and service readiness after an update;
- a controlled maintenance/update window or other approved update policy;
- recovery if an update/reboot does not return the Beelink and Label Print Service to their normal operational state.

## Shared Production Working Tree

Verified from the office-PC session against the UNC share:

```text
Repo root: //print-server/MSB_LabelService
Remote: https://github.com/Gregovate/MSB_LabelPrintService.git
Branch: main
HEAD: 2ec15fcf9fd39230dfb4aba32721e72e8697b0b4
Status: main...origin/main
```

Current service source visible through that share:

```text
label_poll_service_v3.py
SERVICE_VERSION = 3.4
SHA-256 = DFE48D51D4213313F47738B09964BCDFB4788A8B83D5D4CB6130443E7EA3C1BD
```

This is strong evidence that the production share contains the source baseline just pushed to Git. The actual execution command and Python interpreter must still be verified **on `PRINT-SERVER` itself**.

## Protected Configuration

A live configuration file exists in the shared production tree:

```text
\\print-server\MSB_LabelService\config.local.ini
```

Observed metadata:

```text
size: 1050 bytes
last modified: 2026-03-27 17:08:38 local time
```

Its contents were deliberately not displayed.

`config.local.ini` contains protected runtime configuration and must remain outside Git.

## Current Brother Templates

The shared production tree contains:

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

Do not change template object names or template files during engineering recovery.

## Logs / Runtime Evidence

The shared `logs/` directory contains substantial production history and is consistent with the v3.4 rotating-log implementation.

Observed rotation state included:

```text
label_service.log       197971 bytes   modified 2026-08-11 22:42:52
label_service.log.1     5242831 bytes  modified 2026-08-11 18:54:20
label_service.log.2     5242807 bytes  modified 2026-07-31 21:24:18
...
label_service.log.10    5242869 bytes  modified 2026-05-10 13:55:38
```

The v3.4 startup records identify `PRINT-SERVER` as the execution hostname. Recovered startup entries include:

```text
2026-05-18 08:18:41  PRINT-SERVER PID 8220
2026-06-15 09:31:06  PRINT-SERVER PID 9176
2026-06-16 13:06:10  PRINT-SERVER PID 1636
2026-06-16 13:21:11  PRINT-SERVER PID 23692
2026-06-16 13:38:32  PRINT-SERVER PID 24408
2026-06-23 08:52:03  PRINT-SERVER PID 96
2026-07-27 15:46:06  PRINT-SERVER PID 172548
2026-07-28 10:23:18  PRINT-SERVER PID 181380
2026-08-11 15:47:06  PRINT-SERVER PID 12876
```

The most recent log tail shows the service operating normally through:

```text
2026-08-11 22:42:52
```

Immediately before logging stopped, the service was polling PostgreSQL every 15 seconds, reporting zero pending Display and Container labels, and entering its normal idle state. The recovered final log lines contain no application exception, PostgreSQL failure, printer failure, failed-batch loop, or other service-level error.

Therefore the evidence establishes:

- v3.4 was healthy and idle immediately before logging stopped;
- logging ceased after 2026-08-11 22:42:52;
- no later v3.4 startup entry was found in the retained logs during the 2026-08-22 reconnaissance.

The evidence does **not** establish why the process stopped or whether a Windows Update/reboot caused this specific occurrence. That causal relationship must not be documented as fact until direct Beelink evidence supports it.

The shared `state/` directory was empty at the time of inspection.

## Spooler-Recovery Artifacts

Current source includes:

```text
KillSpooler.lnk
killspooler.bat
killspooler.ps1
```

The batch/PowerShell utilities stop the Windows Spooler, delete queued spool files, and restart the spooler.

They are **destructive recovery tools** because queued jobs are discarded. They must not be used as normal startup behavior without reconciling physical print state and PostgreSQL batch/request state.

## Current Architecture Evidence

Current source and recovered operational evidence support this boundary:

```text
Production Database / Directus
    -> PostgreSQL label request and batch state
        -> PRINT-SERVER (192.168.5.56; dedicated Beelink Windows host)
            -> label_poll_service_v3.py (v3.4)
                -> Brother b-PAC3 SDK
                    -> Windows print spooler / PT-P950NW queue
                        -> Brother PT-P950NW
                            -> physical labels
```

The Beelink's exact Windows OS/build, hardware model, local service working path, Python interpreter, b-PAC installation, printer queue configuration, startup launcher, auto-start behavior, and backup/rebuild process still require direct verification on that machine.

## Office-PC Observations — Not Production Authority

The earlier command set established several facts about `MSB-Office-PC`, including Python 3.13.7, a Brother PT-P950NW queue, b-PAC 3.4.0150, and Brother software installations.

These are useful only as workstation/development evidence. They must not be copied into the production print-server runbook unless separately verified on the Beelink host.

Similarly, failure to find the `Start Label Service` shortcut or an auto-start task on `MSB-Office-PC` says nothing about whether those items exist on `PRINT-SERVER`.

## Documentation Drift Confirmed

The March documentation remains useful engineering evidence but is not fully current.

Confirmed or suspected drift includes:

- root README previously referenced v2 even though current source is v3.4;
- `How_Label_Service_Works.md` predates v3.3/v3.4 reliability changes;
- the March TODO describes requester attribution as future work even though v3.2 implemented it;
- the current dedicated Beelink host, startup behavior, Windows Update/restart risk, backup/rebuild procedure, and post-reboot recovery are not adequately documented.

Do not delete the March documents. Reconcile them after the Beelink runtime is verified.

## Exact Next Recovery Step

Remote reconnaissance from `MSB-Office-PC` is now intentionally stopped. SMB access has provided the source, log, hostname, and network baseline, while WinRM is not enabled. Do not enable remote-management services merely to continue this recovery.

When direct access to `PRINT-SERVER` is available, capture read-only:

1. Windows OS/version/build and Beelink hardware model;
2. local path corresponding to `\\print-server\MSB_LabelService`;
3. current Git branch/HEAD/status locally on the Beelink;
4. Python executable/version actually used by `label_poll_service_v3.py`;
5. running Label Print Service process command line, if active;
6. actual service startup shortcut/launcher, account context, and whether it auto-starts after reboot;
7. b-PAC version/install location;
8. PT-P950NW Windows queue/driver/port;
9. current Windows Update/restart configuration at a non-secret administrative level;
10. machine backup/recovery mechanism, if one already exists.

Then determine why some update/reboot cycles fail to return the Label Print Service to its normal operational state. Do not redesign startup behavior until the current mechanism is documented.

After those facts are known, update this document and the root README before changing service behavior or rewriting the March operator documentation.

## Related Documents

- [Repository engineering handoff](../readme.md)
- [How the Label Service Works](How_Label_Service_Works.md)
- [Print Server Operator Guide](Operator_Label_Printing.md)
- [Label Service TODO / historical limitations](TODO_Label_Service.md)
- [Label Print Service Engineering Rules](../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
