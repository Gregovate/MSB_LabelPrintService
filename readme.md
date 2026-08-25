# MSB Label Print Service

The MSB Label Print Service is the Windows-side printing subsystem that converts Production Database label requests into physical Display and Container labels using Brother b-PAC, the Windows print spooler, and the Brother P-touch PT-P950NW.

## Current State

**Status: OPERATIONAL / UNATTENDED REBOOT RECOVERY VERIFIED / ENGINEERING DOCUMENTATION RECOVERY CONTINUES**

Current source baseline:

```text
Repository: Gregovate/MSB_LabelPrintService
Production/main baseline: 2ec15fcf9fd39230dfb4aba32721e72e8697b0b4
Recovery branch: agent/label-print-service-engineering-recovery
Service source: label_poll_service_v3.py
SERVICE_VERSION: 3.4
SHA-256: DFE48D51D4213313F47738B09964BCDFB4788A8B83D5D4CB6130443E7EA3C1BD
```

No Label Print Service application-code change was required to correct the post-reboot manual-start problem.

## Production Host

The service runs on a dedicated Beelink Windows host:

```text
Hostname: PRINT-SERVER
IPv4: 192.168.5.56
Windows account: PRINT-SERVER\Print Service
Local working directory: C:\MSB_LabelService
SMB share: \\print-server\MSB_LabelService
Python: C:\Program Files\Python\python.exe
```

Credential material and the protected production `config.local.ini` must never be committed.

## Current Startup / Recovery Model

Direct PRINT-SERVER reconnaissance on 2026-08-24 established that the original startup method was entirely manual:

```text
Windows reboot
    -> user logs into Windows
    -> user starts desktop launcher
    -> C:\start_label_service.bat
    -> Python starts label_poll_service_v3.py
```

No existing Label Print Service Scheduled Task, Startup-folder entry, or Run-registry entry existed.

The accepted production runtime is now:

```text
Windows reboot/update
    -> Windows Print Spooler starts automatically
    -> Microsoft OpenSSH Server starts automatically
    -> Scheduled Task "MSB Label Service" starts automatically
    -> C:\Program Files\Python\python.exe
       C:\MSB_LabelService\label_poll_service_v3.py
    -> PostgreSQL polling resumes
    -> Brother b-PAC / Windows spooler / PT-P950NW printing operates normally
```

**No interactive Windows desktop login is required for normal Label Print Service operation after reboot.**

Final unattended reboot acceptance passed on **2026-08-24**: `PRINT-SERVER` was rebooted, nobody logged into Windows to start the service, the Scheduled Task started v3.4 automatically, and a real physical label printed successfully after reboot.

## Approved Additional Runtime — Pending Deployment

On 2026-08-25, `PRINT-SERVER` was selected as the permanent production host
for the MSB LOR operator runner. The runner currently associated with
`MSB-OFFICE-PC` was a temporary/test deployment and is not the accepted
long-term production boundary.

This decision does **not** mean the LOR runner is already installed or accepted
on PRINT-SERVER. The transfer remains pending verification of headless access
to the approved LOR preview/state/output paths, an independent Python/runtime
deployment, restricted TCP 8791 connectivity, protected credential creation,
controlled Linux re-pairing, and unattended reboot acceptance.

The LOR runner must use a separate Scheduled Task, process, working directory,
credentials, listener, and logs. It must not be combined with or modify the
working `MSB Label Service` task and printing runtime.

See [Print Server Runtime Runbook](docs/Print_Server_Runtime_Runbook.md) for
the controlled prerequisites and acceptance gates. The LOR runner application
and operator workflow remain owned by
[`Gregovate/MSB-Production-Database-Project`](https://github.com/Gregovate/MSB-Production-Database-Project).

## Start Here

For current runtime administration and engineering recovery, read:

1. [System Documentation](System_Documentation/README.md)
2. [Label Print Service Engineering Rules](System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
3. [PRINT-SERVER SSH Remote Administration Runbook](docs/SSH_Remote_Administration_Runbook.md) — exact SSH login, host verification, remote reboot, reconnect, and post-reboot service checks.
4. [Print Server Runtime Runbook](docs/Print_Server_Runtime_Runbook.md) — Scheduled Task configuration, service verification, printer checks, fallback start, troubleshooting, and reboot acceptance.
5. [Runtime Recovery — 2026-08-24](docs/Label_Print_Service_Runtime_Recovery_2026-08-24.md) — current direct-host engineering checkpoint and evidence.
6. [Runtime Recovery — 2026-08-22](docs/Label_Print_Service_Runtime_Recovery_2026-08-22.md) — historical checkpoint before direct Beelink access.
7. [How the Label Service Works](docs/How_Label_Service_Works.md) — older architecture evidence that still requires reconciliation against v3.4.
8. [Historical Print Server Operator Guide](docs/Operator_Label_Printing.md) — March guide; its requirement to keep the blue console window open is no longer the normal production startup model.

## SSH Quick Reference

From `MSB-Office-PC`:

```powershell
Test-NetConnection 192.168.5.56 -Port 22
ssh -l "Print Service" 192.168.5.56
```

After login, verify the destination:

```cmd
hostname
whoami
```

Expected:

```text
PRINT-SERVER
print-server\print service
```

To reboot `PRINT-SERVER` remotely:

```cmd
shutdown /r /t 0
```

The SSH connection will reset as Windows restarts. After approximately 60-90 seconds, reconnect with:

```powershell
ssh -l "Print Service" 192.168.5.56
```

The complete procedure and verification commands are in [PRINT-SERVER SSH Remote Administration Runbook](docs/SSH_Remote_Administration_Runbook.md).

## Current Scheduled Task

Production task name:

```text
MSB Label Service
```

Verified principal:

```text
UserId    : Print Service
LogonType : Password
RunLevel  : Highest
```

Production action:

```text
Program/script: C:\Program Files\Python\python.exe
Arguments:      C:\MSB_LabelService\label_poll_service_v3.py
Start in:       C:\MSB_LabelService
```

The **Start in** field must not contain quotation marks. The startup trigger uses a one-minute delay.

The historical interactive launcher remains:

```text
C:\start_label_service.bat
```

It is a fallback only; it is not the normal unattended startup path.

## Verified Runtime Evidence — 2026-08-24

Before an interactive Windows desktop login:

- OpenSSH returned automatically after reboot;
- Windows Print Spooler was `Running / Automatic`;
- Brother PT-P950NW queue reported `Normal`;
- Brother printer port was `192.168.5.12_1`;
- v3.4 successfully ran through SSH without Explorer/Desktop;
- PostgreSQL health checks and actor resolution passed;
- a real Container label physically printed in the headless SSH test;
- a real Display label physically printed from the Scheduled Task execution context;
- a real label physically printed after the final unattended reboot test.

These tests establish that Python, PostgreSQL, b-PAC, the Windows spooler, and the Brother PT-P950NW do not require a logged-in Windows desktop for production operation.

## System Boundary

The service is an **External Supporting Subsystem** of the MSB Production Database.

```text
Directus / Production Database
    -> PostgreSQL label request + batch contracts
        -> PRINT-SERVER
            -> MSB Label Print Service v3.4
                -> Brother b-PAC
                    -> Windows print spooler
                        -> Brother PT-P950NW
                            -> physical labels
```

### Production Database owns

- permanent Display and Container identity;
- label-request state;
- PostgreSQL batch/history and audit contracts;
- database business rules;
- normal operator action for requesting labels in Directus.

### This repository owns

- Label Print Service source;
- service-specific SQL/CSV/template handling;
- b-PAC interaction;
- Windows-spooler verification logic;
- service logging and print-storm safety behavior;
- service-specific troubleshooting;
- dedicated PRINT-SERVER runtime/startup/recovery documentation;
- engineering handoff for this subsystem.

## Important Current Source Behavior

Current v3.4 behavior includes:

- PostgreSQL polling every 15 seconds;
- Display and Container label requests;
- snapshot batch creation;
- one physical label per Display;
- two physical labels per Container;
- Brother b-PAC template population and submission;
- Windows spooler verification as the authoritative print-completion signal;
- active PRINTING-batch and nonempty-printer-queue guards;
- requester/actor attribution introduced in v3.2;
- failed-batch persistence and repeated-print-storm protection introduced in v3.3;
- rotating service logs introduced in v3.4.

Do not weaken the failed-batch, queue, spooler-verification, transaction, or retry safeguards during recovery work.

## Safety Boundaries

### Repeated-print protection

The April 2026 print-storm correction is a critical production safety boundary. Failed batches must remain durable so the same active request cannot silently requeue and print repeatedly.

### Spooler clearing

`killspooler.bat` and `killspooler.ps1` intentionally discard queued Windows print jobs. They are destructive recovery tools, not normal startup behavior. Reconcile physical print state and PostgreSQL batch/request state before using them.

### Credentials

Never commit:

- Windows passwords;
- database passwords;
- `config.local.ini` production secrets;
- private keys;
- tokens or other authentication material.

## Documentation State

The 2026-08-24 direct-host recovery supersedes several stale assumptions in the March-era documentation.

Known drift still requiring reconciliation includes:

- the historical operator guide says the blue console must remain open;
- older architecture/TODO material predates v3.3/v3.4 reliability changes;
- Beelink hardware and full installed-runtime inventory are not yet complete;
- Windows Update policy still needs a deliberate maintenance policy even though unattended reboot recovery now works;
- machine backup/rebuild documentation remains incomplete.

Do not delete useful historical documents merely because newer documents supersede part of their content.

## Remaining Recovery Work

The post-reboot startup problem is resolved. Remaining engineering reconnaissance includes:

- exact Beelink hardware model;
- exact Brother b-PAC installed version/location on PRINT-SERVER;
- complete Brother driver details beyond the verified queue and port;
- Windows Update configuration/history and controlled maintenance policy;
- machine backup/rebuild/recovery mechanism;
- reconciliation of `docs/How_Label_Service_Works.md`, `docs/Operator_Label_Printing.md`, and `docs/TODO_Label_Service.md`;
- reciprocal handoff updates to related MSB repositories where appropriate;
- controlled deployment and acceptance of the independently hosted LOR runner
  on PRINT-SERVER, including durable headless access to its Google Drive data
  paths and removal of the temporary MSB-OFFICE-PC listener after cutover.

Do not redesign the working label-printing application while completing this recovery inventory.

## Resume Development

Resume from:

```text
agent/label-print-service-engineering-recovery
```

Use the current runbooks and 2026-08-24 recovery checkpoint as authority for PRINT-SERVER startup and SSH behavior. Use the live production system as authority when remaining runtime facts conflict with older documentation.

## Related Systems

- [MSB Production Database Project](https://github.com/Gregovate/MSB-Production-Database-Project)
- [MSB Server Management](https://github.com/Gregovate/MSB-Server-Management)

## Maintainer

Greg Liebig / Engineering Innovations, LLC / Making Spirits Bright
