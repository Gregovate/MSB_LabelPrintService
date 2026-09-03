# V4 Controlled Production Deployment and Queue Plan

| Document Control | Value |
|---|---|
| Document Type | Engineering deployment record and active design contract |
| System | MSB Label Print Service / PRINT-SERVER |
| Status | CURRENT — controlled V4 production use |
| Effective Date | 2026-09-03 |
| Controlling Issue | [#14](https://github.com/Gregovate/MSB_LabelPrintService/issues/14) |
| Pull Request | [#15](https://github.com/Gregovate/MSB_LabelPrintService/pull/15) |

## Deployment Decision

V4 is installed as the production `MSB Label Service` Scheduled Task worker before the Controller, Location, and Wiring polling paths are added.

The purpose is to place the already-working Display and Container workload on V4's stronger media preflight and batch-safety behavior while development continues. PR #15 remains draft and V3.4 remains the rollback version.

V3 and V4 must never run concurrently.

## Verified Cutover — 2026-09-03

Scheduled Task action:

```text
Execute:          C:\Program Files\Python\python.exe
Arguments:        "C:\MSB_LabelService\label_poll_service_v4.py"
WorkingDirectory: C:\MSB_LabelService
Principal:        Print Service
LogonType:        Password
RunLevel:         Highest
```

Startup evidence:

- task state: `Running`;
- Task Scheduler result: `267009` / `0x41301` (currently running);
- process: `label_poll_service_v4.py`, PID `18248`;
- no V3 label-service process;
- V4 logged successful 15-second polling;
- pending workload at cutover: zero Displays and zero Containers;
- V3 task XML preserved at `C:\MSB_LabelService\state\MSB_Label_Service_v3_task_20260902.xml`.

This checkpoint proves Scheduled Task startup and database polling. It does not yet prove a physical Display/Container print from the Scheduled Task context or unattended reboot recovery.

## Polling and Scheduling Contract

The worker continues polling every 15 seconds. Polling must not create a message every 15 seconds.

The operational rule is:

> Print every compatible workload that can run safely, and stop only the printer/family that cannot proceed.

Before creating an execution batch, the worker must validate:

- configured printer and template;
- required media family;
- Brother status;
- Windows printer queue;
- runtime directories and SQL/CSV paths;
- absence of an unresolved active/failed batch for that printer.

If preflight fails:

- create no execution batch;
- leave the request pending;
- record the blocked state;
- notify only when the blocking condition is new or changes;
- do not open repeated dialogs for the unchanged request set;
- continue independent work on another printer.

The PT-P950NW has one installed cassette. Pending P950 work must be grouped by media requirement:

- 36 mm laminated: Display and Container families;
- 24 mm laminated: Display and Controller families;
- 12 mm laminated: Wiring fold-over family.

The QL-820NWB Location workload is independent and requires DK-2251 62 mm / marketed 2.4-inch red-black continuous media.

## Print-Server Job Dashboard

The headless Scheduled Task worker must not own the interactive user interface. Its `LogonType: Password` execution can run without an interactive Windows desktop, so worker-side message boxes are not reliable operator feedback.

A separate interactive dashboard will run when the Print Service user logs in. Closing or crashing the dashboard must not stop polling or printing.

The table will show at minimum:

- printer;
- label family;
- required media;
- pending quantity;
- active batch;
- current state;
- blocking reason;
- first-seen and last-changed timestamps;
- available Retry and Hold/Cancel actions.

The dashboard updates silently on each poll. It may flash or sound once when a blocking condition first appears or materially changes.

Preflight Cancel/Hold dismisses the alert and leaves requests pending. It does not mark anything printed.

## Low-Tape and Tape-Out Contract

A recovery-required batch is not the desired normal response to cartridge exhaustion.

The controlled investigation must:

1. use a cassette approaching the striped end-marker region;
2. submit one physical label at a time;
3. wait for physical/spooler completion;
4. capture and retain the full raw Brother status before and after each label;
5. continue through the striped warning region and final exhaustion;
6. identify whether a stable low-tape signature appears before `error1=0x02`;
7. document the exact boundary label and spooler behavior.

If a reliable warning exists, production must stop before submitting the next label and leave remaining requests pending.

The existing V4 loop currently submits multiple `PrintOut()` calls before waiting for the spooler. Merely inserting immediate status queries into that tight loop may capture submission timing rather than physical tape advancement. Per-label serialization must therefore be proven during the controlled test.

An unresolved/recovery-required batch remains only the safety fallback for an unexpected mid-label failure or if Brother exposes no usable advance warning. The system must never guess which boundary label physically printed or blindly resend the whole batch.

## Request Pipelines

| Family | Request source | Current state |
|---|---|---|
| Display | `ref.display.print_label` | V4 implemented |
| Container | `ref.container.print_label` | V4 implemented |
| Controller | `ref.request_controller_label(p_email, p_controller_id)` sets `ref.controller.print_label` | governed request/route deployed; gated V4 consumer implemented but disabled pending DB migration and acceptance |
| Location | governed request on `ref.storage_location` | request field/command and V4 consumer missing |
| Wiring | purpose-built operational request queue | physical format approved; request workflow and V4 consumer missing |

The Controller request and scan contracts are authoritative and deployed; see [Controller Label Request and Physical Format Contract](Controller_Label_Request_and_Physical_Format_Contract_2026-09-03.md). The draft V4 branch now implements the Controller poll/snapshot/render/finalization path behind a feature flag that defaults to off. Production activation still requires the Controller batch migration, pending-request review, and controlled physical/restart/no-double-print acceptance.

Location and Wiring still require governed request contracts as well as their service consumers. The 12 mm fold-over Wiring physical format and direct b-PAC print path are approved; this approval does not create the missing request/polling pipeline.

The FieldWiring application owns creating Wiring requests. LabelPrintService owns consuming them and all Brother printer interaction.

## Remaining Controlled Acceptance

- one Display physical print from the V4 Scheduled Task;
- one Container physical print from the V4 Scheduled Task;
- V3.4 rollback exercise;
- unattended reboot and V4 restart verification;
- Controller request-to-print pipeline;
- Location request-to-print pipeline;
- Wiring request-to-print pipeline using the approved 12 mm fold-over format;
- print-job dashboard;
- low-tape/end-marker capture;
- safe stop-before-next-label behavior if a warning signature is found;
- Display/Container regressions after shared scheduler changes.

Do not merge PR #15 until the controlling acceptance work is complete.
