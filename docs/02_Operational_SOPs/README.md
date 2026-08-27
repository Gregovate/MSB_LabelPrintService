# MSB Label Print Service — Operational SOPs

| Document Control | Value |
|---|---|
| Document Type | README / Documentation Portal |
| System | MSB Label Print Service / PRINT-SERVER |
| Audience | Operators, MSB Database Administrator, Print Server Maintainer |
| Status | CURRENT |
| Last Reviewed | 2026-08-27 |

Use this folder for operational procedures. Engineering architecture and implementation details belong under `docs/01_Engineering/` or the repository-specific engineering rules.

## Current Procedures

- [Failed Batch and Print Service Recovery](Failed_Batch_and_Print_Service_Recovery.md) — start/stop/status, live log, `FAILED` batch recovery, template-path recovery, PT-P950NW media verification, and safe retry rules.
- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md) — PRINT-SERVER runtime, Scheduled Task, SSH administration, reboot recovery, and spooler/runtime verification.
- [Operator Label Printing](Operator_Label_Printing.md) — normal operator-facing label-print workflow.
- [SSH Remote Administration Runbook](SSH_Remote_Administration_Runbook.md) — remote PRINT-SERVER administration.

## Historical / Recovery Records

- [Runtime Recovery — 2026-08-24](Label_Print_Service_Runtime_Recovery_2026-08-24.md)
- [Runtime Recovery — 2026-08-22](Label_Print_Service_Runtime_Recovery_2026-08-22.md)

Historical recovery records preserve evidence and should not replace the current procedure when a current SOP exists.
