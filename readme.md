# MSB Label Print Service

The MSB Label Print Service is the Windows-side printing subsystem that converts Production Database label requests into physical Display and Container labels using Brother b-PAC, the Windows print spooler, and the Brother P-touch PT-P950NW.

## Current State

**Status: OPERATIONAL SYSTEM / ENGINEERING RECOVERY AND DOCUMENTATION IN PROGRESS**

The current Git source baseline was refreshed from the MSB office PC on 2026-08-22. The current service source is:

```text
label_poll_service_v3.py
SERVICE_VERSION = 3.4
SHA-256 = DFE48D51D4213313F47738B09964BCDFB4788A8B83D5D4CB6130443E7EA3C1BD
```

The production Label Print Service host is **not MSB-Office-PC**. It is a separate dedicated **Beelink Windows machine** whose service-recorded Windows hostname is:

```text
PRINT-SERVER
```

From `MSB-Office-PC`, `print-server.localdomain` resolves to `192.168.5.56`, and the production working tree is accessible through:

```text
\\print-server\MSB_LabelService
```

The Beelink has a password-protected Windows account named `printserver`. Credential material is not documentation data and must not be committed to Git. The account's exact role in service startup and post-reboot recovery still requires direct verification on `PRINT-SERVER`.

Important current source behavior includes:

- polling PostgreSQL for pending Display and Container label requests;
- snapshot batch creation before physical printing;
- one physical label per Display;
- two physical labels per Container;
- Brother b-PAC template population and job submission;
- Windows spooler verification as the authoritative print-completion signal;
- active-printing-batch and nonempty-queue guards;
- requester/actor attribution added in v3.2;
- failed-batch persistence / repeated-print-storm protection added in v3.3;
- rotating service logging added in v3.4;
- explicit spooler-recovery scripts present in the current source tree.

The most recent retained runtime evidence shows v3.4 starting on `PRINT-SERVER` on 2026-08-11 at 15:47:06 and then polling PostgreSQL normally every 15 seconds through 22:42:52. The final retained log lines show zero pending labels and normal idle state, with no application, database, printer, or failed-batch error immediately before logging stopped. No later startup entry was found in the retained logs during the 2026-08-22 reconnaissance. The cause of that stop has **not** been established.

A known production reliability issue is that automatic Windows Updates are enabled on the dedicated Beelink print server and, after some Microsoft-pushed updates, the machine does not restart cleanly or return the Label Print Service to its normal operational state without intervention. This is a restart/recovery issue, not a crash condition. The current engineering recovery must document the existing update/reboot behavior and establish a deliberate recovery/update policy before Setup season.

No service redesign or production behavior change is approved as part of the current recovery work.

## Start Here

- [System Documentation](System_Documentation/README.md) — reusable MSB standards and Label Print Service-specific engineering rules.
- [Label Print Service Engineering Rules](System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md) — required engineering, runtime, rollback, print-storm, and documentation safeguards.
- [Runtime Recovery — 2026-08-22](docs/Label_Print_Service_Runtime_Recovery_2026-08-22.md) — current source/runtime evidence, `PRINT-SERVER` host boundary, Windows Update/restart risk, and exact remaining reconnaissance.
- [How the Label Service Works](docs/How_Label_Service_Works.md) — March 2026 architecture description; useful historical/current evidence but requires reconciliation against v3.4 and the live Beelink runtime.
- [Print Server Operator Guide](docs/Operator_Label_Printing.md) — March operator/admin guide; requires live-runtime verification before being treated as fully current.

## System Boundary

The service is an **External Supporting Subsystem** of the MSB Production Database.

```text
Directus / Production Database
    -> PostgreSQL label request + batch contracts
        -> PRINT-SERVER (dedicated Beelink Windows host)
            -> MSB Label Print Service
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

- polling-service source;
- service-specific SQL/CSV/template handling;
- b-PAC interaction;
- Windows-spooler verification logic;
- service logging and safety behavior;
- service-specific operator troubleshooting;
- source/deployment engineering handoff;
- dedicated Beelink print-server runtime/recovery documentation for this service.

The generic MSB server-management repository may link to this subsystem, but the LabelPrintService repository remains the primary owner of this dedicated application's Windows runtime because the machine exists to run this service.

## Current Source Layout

Important current repository areas include:

```text
label_poll_service_v3.py       current service source (v3.4)
label_poll_service_v1.py       historical source
label_poll_service_v2.py       historical source
bpac_*                         b-PAC test/smoke utilities
confirm_last_batch.py          batch recovery/confirmation utility
fail_last_batch.py             batch failure utility
killspooler.bat                destructive spooler recovery utility
killspooler.ps1                destructive spooler recovery utility
templates/                     Brother .lbx templates
sql/                           database queries/contracts consumed by service
csv/                           generated/current working CSV artifacts
logs/                          runtime logs when present
state/                         service state when present
config.example.ini             non-secret configuration example
config.local.ini               protected live configuration; must not be committed
System_Documentation/          engineering/documentation governance
```

## Safety Boundaries

### Repeated-print protection

The April 2026 print-storm correction is a critical production safety boundary. Failed batches must remain durable so the same active request cannot silently requeue and print repeatedly.

Do not change transaction boundaries, failed-batch guards, automatic retry behavior, spooler verification, or original `print_label` flag clearing without explicit review and regression testing.

### Spooler clearing

`killspooler.bat` and `killspooler.ps1` intentionally discard queued Windows print jobs.

They are recovery tools, not normal startup behavior. Before using them, confirm queued jobs may safely be lost and reconcile PostgreSQL batch/request state afterward so physical labels are not duplicated.

### Windows Update / reboot

The dedicated Beelink has a known post-update restart/recovery weakness. Do not simply disable security updates during recovery. Establish and document a controlled update/reboot/recovery process that verifies the Label Print Service, PostgreSQL access, b-PAC, printer queue, and physical printer after restart.

### Secrets

Never commit the live `config.local.ini`, database passwords, Windows credentials, private keys, tokens, or other protected authentication material.

## Documentation State

The original March documentation captured the initial architecture and operator workflow but predates later service changes and the current documentation standards.

Known documentation drift includes:

- root README previously instructed `label_poll_service_v2.py` even though current source is v3.4;
- March architecture/TODO material predates later requester-attribution work;
- March documentation predates the v3.3 repeated-print-storm fix;
- March documentation predates v3.4 rotating logging;
- the dedicated Beelink installation/startup/update/rebuild details are not adequately documented.

Do not rewrite historical evidence to make it appear current. Reconcile current documents deliberately after direct Beelink inspection.

## Authoritative Sources

Before changing service behavior, review:

1. `label_poll_service_v3.py` — current Git implementation baseline;
2. current files under `sql/` and `templates/`;
3. [Runtime Recovery — 2026-08-22](docs/Label_Print_Service_Runtime_Recovery_2026-08-22.md);
4. the current Production Database Labeling/Scanning integration contract;
5. the dedicated Beelink print server when deployment/runtime behavior matters;
6. [Label Print Service Engineering Rules](System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md).

## Known Open Work

Remote reconnaissance from `MSB-Office-PC` is complete for now. `PRINT-SERVER` is reachable over SMB, while WinRM is not enabled. Do not enable remote-management services merely to continue documentation recovery.

Current engineering recovery must still, when direct access to `PRINT-SERVER` is available:

- verify its Windows OS/build and Beelink hardware model;
- verify the local path behind `\\print-server\MSB_LabelService`;
- verify the Python interpreter/environment actually used by the service;
- document the actual service startup shortcut/launcher, `printserver` account context, and auto-start behavior;
- document b-PAC installation/version on the Beelink;
- document the Beelink's Brother driver, Windows queue, and PT-P950NW network relationship;
- document protected configuration location without exposing secrets;
- document log/state locations and retention;
- document safe service restart and spooler recovery procedures;
- document Windows Update/reboot behavior and post-update recovery;
- document backup/rebuild/rollback of the Beelink print server;
- determine why some restart/update cycles fail to return the Label Print Service to normal operation;
- reconcile `docs/How_Label_Service_Works.md`, `docs/Operator_Label_Printing.md`, and `docs/TODO_Label_Service.md` with accepted current behavior;
- update reciprocal handoffs in `MSB-Production-Database-Project` when recovery is complete.

## Resume Development

Resume from branch:

```text
agent/label-print-service-engineering-recovery
```

Read, in order:

1. [System Documentation](System_Documentation/README.md)
2. [Label Print Service Engineering Rules](System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
3. [Runtime Recovery — 2026-08-22](docs/Label_Print_Service_Runtime_Recovery_2026-08-22.md)
4. this README
5. `label_poll_service_v3.py`
6. the current `docs/` architecture/operator material
7. the responsible Production Database Labeling/Scanning handoff

Then inspect `PRINT-SERVER` **read-only** when direct access is available and promote the verified runtime facts into Git before changing production behavior.

Material work is not complete until this README is reviewed and updated with the resulting current state and exact next resume point.

## Related Systems

- [MSB Production Database Project](https://github.com/Gregovate/MSB-Production-Database-Project)
- [MSB Server Management](https://github.com/Gregovate/MSB-Server-Management)

## Maintainer

Greg Liebig / Engineering Innovations, LLC / Making Spirits Bright
