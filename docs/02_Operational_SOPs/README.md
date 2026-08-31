# MSB Label Print Service — Operational SOPs

| Document Control | Value |
|---|---|
| Document Type | README / Documentation Portal |
| System | MSB Label Print Service / PRINT-SERVER |
| Audience | Operators, MSB Database Administrator, Print Server Maintainer |
| Status | CURRENT |
| Last Reviewed | 2026-08-31 |

Use this folder for operational procedures. Engineering architecture and implementation details belong under `docs/01_Engineering/` or the repository-specific engineering rules.

## Current Procedures

- [Failed Batch and Print Service Recovery](Failed_Batch_and_Print_Service_Recovery.md) — start/stop/status, live log, `FAILED` batch recovery, template-path recovery, PT-P950NW media verification, and safe retry rules.
- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md) — PRINT-SERVER runtime, Scheduled Task, SSH administration, reboot recovery, and spooler/runtime verification.
- [Operator Label Printing](Operator_Label_Printing.md) — current normal operator-facing label-print workflow.
- [Label Service v4 — Printer Recovery and Tape-Out SOP](Label_Service_v4_Printer_Recovery.md) — **PRE-RELEASE** v4 Retry/Cancel/Resume behavior for wrong media, no media, cover open, unavailable printer, unsafe queue, and tape-out during an active batch.
- [SSH Remote Administration Runbook](SSH_Remote_Administration_Runbook.md) — remote PRINT-SERVER administration.

## Historical / Recovery Records

- [Runtime Recovery — 2026-08-24](Label_Print_Service_Runtime_Recovery_2026-08-24.md)
- [Runtime Recovery — 2026-08-22](Label_Print_Service_Runtime_Recovery_2026-08-22.md)

Historical recovery records preserve evidence and should not replace the current procedure when a current SOP exists.

## Documentation Rule

Operational behavior accepted during engineering must be promoted into the appropriate current SOP before deployment. Issue comments and chat history are evidence only and must not be the sole operator instructions.
