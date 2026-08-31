# MSB Label Print Service v4 — Printer Recovery and Tape-Out SOP

| Document Control | Value |
|---|---|
| Status | PRE-RELEASE — use for v4 acceptance/training only until v4 is deployed |
| System | PRINT-SERVER / MSB Label Print Service v4 |
| Last Updated | 2026-08-31 |
| Related Engineering Contract | `docs/01_Engineering/Label_Service_v4_Architecture_and_Acceptance.md` |

## Purpose

This SOP defines how PRINT-SERVER operators should respond to the visible v4 printer-recovery dialogs for wrong cassette, no media, cover open, printer unavailable, unsafe queue, and tape-out during an active batch.

The goal is to correct ordinary printer problems without creating failed PostgreSQL batches or requiring DBA cleanup.

## Normal Preflight Recovery

For correctable problems discovered before a batch is created, v4 must show a visible dialog on the PRINT-SERVER Beelink.

Example:

```text
MSB Label Service

Wrong tape cassette loaded.

Required: 24 mm laminated tape
Detected: 36 mm laminated tape

Change the cassette and close the cover,
then press Retry to continue.

[ Retry ]   [ Cancel ]
```

### Operator action

1. Read the required media shown in the dialog.
2. Correct the physical condition.
3. Close the printer cover.
4. Press **Retry**.
5. Do not re-request the label in Directus while the dialog is active.

### Retry behavior

`Retry` reruns full preflight. It does not create a batch merely because the operator pressed Retry.

If the condition is still wrong, the service remains in the recovery path and reports the current condition.

### Cancel behavior

Press **Cancel** when the requested print should not continue at this time.

Cancel must:

- stop the current preflight attempt;
- return the service safely to idle;
- leave source `print_label` requests untouched;
- create no batch header/items;
- require no PostgreSQL cleanup.

## Wrong Cassette

The dialog should state both required and detected media when detection is available.

Examples:

```text
Required: 36 mm laminated tape
Detected: 24 mm laminated tape
```

or

```text
Required: 12 mm laminated tape
Detected: 36 mm laminated tape
```

Replace the cassette with the required width, close the cover, and press **Retry**.

## No Cassette / No Media

Install the required cassette, close the cover, and press **Retry**.

Do not repeatedly toggle the Directus Print Label request.

## Cover Open

Close the printer cover and press **Retry**.

The service should not infer media identity while the cover-open status prevents reliable media reporting.

## Printer Unavailable

Confirm:

- printer power is on;
- network cable/network connection is present;
- printer is reachable on the expected network;
- Windows printer queue exists on PRINT-SERVER.

After correcting the condition, press **Retry**.

If the printer cannot be restored promptly, press **Cancel** and report the condition.

## Unsafe / Non-Empty Windows Queue

Do not submit another print batch while the queue is in an unsafe or ambiguous state.

If v4 displays a queue-intervention dialog:

1. inspect the queue on PRINT-SERVER;
2. determine whether a legitimate active job is still processing;
3. do not delete jobs merely to make the warning disappear unless directed by the recovery runbook;
4. press **Retry** only after the queue is known safe;
5. otherwise press **Cancel** and escalate.

## Tape-Out During an Active Batch

Tape-out is different from preflight because an execution batch already exists and some labels may already have physically printed.

When v4 detects Brother **End of media**, it must stop blindly advancing and display a recovery dialog such as:

```text
MSB Label Service

Tape cassette is empty.

Replace with 36 mm laminated tape.
Close the cover.

[ Resume ]   [ Cancel ]
```

### Operator action

1. Note the label that was physically printing or the last label visibly produced.
2. Replace the cassette with the width shown by the dialog.
3. Close the cover.
4. Press **Resume**.
5. Report the observed boundary label to Greg so the service logs can be correlated with the real printer behavior.

### Resume behavior

Before continuing, Resume must recheck:

- printer reachability;
- correct cassette width/type;
- cover state;
- printer readiness.

Do not press Resume until the correct cassette is installed and the cover is closed.

### Boundary-label rule

Until controlled evidence proves otherwise, the label that was printing when tape ran out is considered **uncertain**.

Do not assume v4 should automatically reprint it. Brother/P-touch behavior suggests the printer/driver may resume or replay the interrupted label, but the exact b-PAC + Windows spooler behavior must be proven from a real event.

The service will log per-label sequence/context specifically so this can be determined when it naturally occurs.

### Cancel during tape-out

Cancel stops the active print path and preserves the batch/log evidence for controlled recovery. Do not manually clear database batch state unless following the current failed-batch/recovery SOP.

## What Staff Should Report After Tape-Out

When tape runs out during a real batch, report at minimum:

- approximate time;
- which printer;
- tape width;
- label visibly printing / last label seen;
- whether a partial label came out;
- what happened after cassette replacement;
- whether the printer automatically printed/reprinted a label before the service was manually restarted or resumed.

This physical observation is needed to interpret the service and Windows logs correctly.

## Logs to Preserve

Do not delete or truncate logs after a printer failure.

Relevant evidence includes:

```text
C:\MSB_LabelService\logs\label_service.log
C:\MSB_LabelService\logs\batches\...
Windows print queue state
Brother raw/SNMP status captured by v4
```

For tape-out, the batch log should identify the exact sequence number, asset ID/name, template family, media requirement, and status around the failure boundary.

## PRINT-SERVER Interactive Session Requirement

Visible v4 dialogs require the service to run in the logged-on Windows session.

PRINT-SERVER autologin is enabled, but v4 deployment acceptance must still verify that the Scheduled Task is configured to run interactively so the dialogs are actually visible on the Beelink screen.

If the service is running but no expected dialog appears during a controlled wrong-media test, stop acceptance and correct the Scheduled Task/session configuration before production use.

## Do Not Do These Things

- Do not repeatedly request the same labels in Directus while a recovery dialog is active.
- Do not assume a cleared Windows spooler proves a physical label printed.
- Do not guess which boundary label printed after tape-out.
- Do not clear failed batch rows directly unless following the controlled recovery SOP.
- Do not switch cassette width and press Resume/Retry without closing the cover and allowing v4 to recheck status.

## Related SOPs

- `Failed_Batch_and_Print_Service_Recovery.md`
- `Print_Server_Runtime_Runbook.md`
- `Operator_Label_Printing.md`
- `../01_Engineering/Label_Service_v4_Architecture_and_Acceptance.md`
