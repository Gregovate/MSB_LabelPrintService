# V4 Controlled Production Deployment and Queue Plan

| Document Control | Value |
|---|---|
| Document Type | Engineering deployment record and active design contract |
| System | MSB Label Print Service / PRINT-SERVER |
| Status | CURRENT — controlled V4 production use |
| Effective Date | 2026-09-03 |
| Baseline Issue | [#14](https://github.com/Gregovate/MSB_LabelPrintService/issues/14) — closed |
| Baseline Pull Request | [#15](https://github.com/Gregovate/MSB_LabelPrintService/pull/15) — merged |

## Deployment Decision

V4 is installed as the production `MSB Label Service` Scheduled Task worker before the Controller, Location, and Wiring polling paths are added.

The purpose is to place the already-working Display and Container workload on V4's stronger media preflight and batch-safety behavior while development continues. PR #15 is merged and V3.4 remains the rollback version.

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

Later 2026-09-03 acceptance proved unattended reboot recovery and production
Controller polling. Candidate `4.1.0-rc2` automatically completed a one-label
batch and, after an offline request buildup, one 13-label batch with 13/13
items, zero pending requests, zero failed batches, and no duplicate output.

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

Candidate `4.1.0-rc3` adds an observation-only 250 ms PT-P950NW sampler around
every Display, Container, and Controller active spooler job. It records the
initial raw packet, every change, five-second heartbeats, query errors/recovery,
and a two-second post-spooler window in the batch log. This closes the missing
evidence-capture gap before the next natural runout.

The existing V4 loop still submits multiple `PrintOut()` calls before waiting
for the spooler. The sampler may therefore capture physical tape advancement
without proving which already-submitted label can still be stopped. Per-label
serialization or another submission checkpoint must be proven after the
warning signature is identified. `4.1.0-rc3` does not automatically stop on an
unknown changed byte.

An unresolved/recovery-required batch remains only the safety fallback for an unexpected mid-label failure or if Brother exposes no usable advance warning. The system must never guess which boundary label physically printed or blindly resend the whole batch.

## Request Pipelines

| Family | Request source | Current state |
|---|---|---|
| Display | `ref.display.print_label` | V4 implemented |
| Container | `ref.container.print_label` | V4 implemented |
| Controller | `ref.request_controller_label(p_email, p_controller_id)` sets `ref.controller.print_label` | request, route, batch schema, V4 consumer, physical print, scan, restart, and 13-label offline recovery accepted |
| Location | governed request on `ref.storage_location` | request field/command and V4 consumer missing |
| Wiring | purpose-built operational request queue | physical format approved; request workflow and V4 consumer missing |

The Controller request, scan, database batch, and physical print contracts are
authoritative, deployed, and accepted; see [Controller Label Request and
Physical Format Contract](Controller_Label_Request_and_Physical_Format_Contract_2026-09-03.md).
The tracked example keeps the feature flag off for safe first installation,
while production `config.v4.local.ini` explicitly enables Controller polling.

Location and Wiring still require governed request contracts as well as their service consumers. The 12 mm fold-over Wiring physical format and direct b-PAC print path are approved; this approval does not create the missing request/polling pipeline.

The FieldWiring application owns creating Wiring requests. LabelPrintService owns consuming them and all Brother printer interaction.

## Remaining Controlled Acceptance

- continued Display and Container production regression monitoring;
- V3.4 rollback exercise;
- Location request-to-print pipeline;
- Wiring request-to-print pipeline using the approved 12 mm fold-over format;
- print-job dashboard;
- deploy and verify `4.1.0-rc3` active-job status capture;
- low-tape/end-marker capture during the next natural runout;
- safe stop-before-next-label behavior if a warning signature is found;
- Display/Container regressions after shared scheduler changes.

PR #15 established the merged V4 Display/Container production baseline. Every
remaining capability is delivered and accepted through its own scoped issue and
pull request.
