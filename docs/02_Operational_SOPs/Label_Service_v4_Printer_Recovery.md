# MSB Label Print Service v4 — Printer Recovery and Tape-Out SOP

| Document Control | Value |
|---|---|
| Status | PRE-RELEASE — use for v4 acceptance/training only until v4 is deployed |
| System | PRINT-SERVER / MSB Label Print Service v4 |
| Last Updated | 2026-09-08 |
| Related Engineering Contract | `docs/01_Engineering/Label_Service_v4_Architecture_and_Acceptance.md` |

## Purpose

This SOP defines how PRINT-SERVER operators should respond to the visible v4
printer-recovery notices for wrong cassette, no media, cover open, printer
unavailable, unsafe queue, and tape-out during an active batch.

The goal is to correct ordinary printer problems without creating failed PostgreSQL batches or requiring DBA cleanup.

## Normal Preflight Recovery

For correctable problems discovered before a batch is created, v4 must show a
visible informational notice on the PRINT-SERVER console and continue checking
the printer automatically.

Example:

```text
MSB Label Service

Wrong tape cassette loaded.

Required: 24 mm laminated tape
Detected: 36 mm laminated tape

Change the cassette and close the cover.
Printing will resume automatically after the
correct cassette is detected and the printer is idle.

[ OK ]
```

### Operator action

1. Read the required media shown in the notice.
2. Correct the physical condition.
3. Close the printer cover.
4. Dismiss the notice when convenient. The button does not control printing.
5. Do not re-request the label in Directus while the request remains pending.

### Automatic retry behavior

The service reruns full preflight on its normal polling interval. It creates no
batch until every preflight check passes.

If the condition is still wrong, the service leaves all requests pending. If
the detected condition changes—for example, an empty slot becomes a 36 mm
cassette while the request requires 24 mm—the service sends a new notice that
states both required and detected media.

### Hold/cancel behavior

Candidate `4.1.0-rc4` does not put a Cancel button in the informational notice.
Dismissal must not silently cancel a database-owned request. A durable Hold or
Cancel action belongs in the operator application/dashboard and remains a
separate capability.

The service does not repeat the same notice on every 15-second poll. Failed
notice delivery is retried at a bounded heartbeat; a materially changed
printer condition sends a new notice immediately.

## Wrong Cassette

The notice must state both required and detected media when detection is available.

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

Replace the cassette with the required width and close the cover. Printing
resumes automatically only when the required width/type is detected.

## No Cassette / No Media

Install the required cassette and close the cover. Printing resumes
automatically after the correct cassette is detected.

Do not repeatedly toggle the Directus Print Label request.

## Cover Open

Close the printer cover. The next normal poll rechecks the cassette and printer
state automatically.

The service should not infer media identity while the cover-open status prevents reliable media reporting.

## Printer Unavailable

Confirm:

- printer power is on;
- network cable/network connection is present;
- printer is reachable on the expected network;
- Windows printer queue exists on PRINT-SERVER.

After correcting the condition, allow one normal polling interval for the
service to recheck automatically.

If the printer cannot be restored promptly, leave the requests pending, stop
requesting additional labels, and report the condition.

## Unsafe / Non-Empty Windows Queue

Do not submit another print batch while the queue is in an unsafe or ambiguous state.

If v4 displays a queue-intervention notice:

1. inspect the queue on PRINT-SERVER;
2. determine whether a legitimate active job is still processing;
3. do not delete jobs merely to make the warning disappear unless directed by the recovery runbook;
4. allow the service to retry only after the queue is known safe;
5. otherwise stop requesting additional labels and escalate.

## Tape-Out During an Active Batch

Tape-out is different from preflight because an execution batch already exists and some labels may already have physically printed.

Candidate `4.1.0-rc4` keeps sampling after the Windows spooler clears until
Brother reaches ready/idle or reports a terminal error. When it detects Brother
**End of media** after all b-PAC submissions and the observed Windows job have
completed, it records the terminal packet and finalizes that submitted batch.
It then leaves later requests pending and displays an informational notice such
as:

```text
MSB Label Service

Tape cassette is empty.

Replace with 36 mm laminated tape.
Close the cover.
Printing will resume automatically.

[ OK ]
```

### Operator action

1. Note the label that was physically printing or the last label visibly produced.
2. Replace the cassette with the width shown by the notice.
3. Close the cover.
4. Wait for the service to resume automatically.
5. Report the observed boundary label to Greg so the service logs can be correlated with the real printer behavior.

### Automatic resume behavior

Before starting the next batch, the service rechecks:

- printer reachability;
- correct cassette width/type;
- cover state;
- printer readiness.

The service must also confirm Brother `phase=0x00`. This prevents a new batch
from starting while the printer/driver is replaying the boundary label from the
replacement cassette.

### Boundary-label rule

The September 8 production runout proved this behavior for a 24 mm Controller
batch: the old cassette printed `CTRL:1098` at the green/racing-stripe boundary,
and the Brother/Windows stack replayed `CTRL:1098` after the new cassette was
installed. That one boundary replay is acceptable.

The Label Service must not submit an additional application-level copy. The
completed source request must remain cleared while later pending requests wait
for correct replacement media.

### If automatic recovery does not occur

Do not clear database state or re-request labels. Preserve the service log,
batch log, Windows queue state, pending request IDs, and non-completed batch
state. Follow the current failed-batch/runtime recovery SOP before stopping or
restarting the worker.

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

## PRINT-SERVER Notice Delivery

The production worker remains a headless password-logon Scheduled Task.
Candidate `4.1.0-rc4` uses Windows Terminal Services to send a non-blocking
message to the active physical console session. The message is informational;
printing recovery must not depend on the operator clicking it.

If no console session is attached, the service logs the failed delivery and
retries at a bounded heartbeat. Controlled acceptance must prove that a
required/detected-media notice appears on the PRINT-SERVER monitor while the
worker remains in Session 0.

## Do Not Do These Things

- Do not repeatedly request the same labels in Directus while a recovery notice is active.
- Do not assume a cleared Windows spooler proves a physical label printed.
- Do not guess which boundary label printed after tape-out.
- Do not clear failed batch rows directly unless following the controlled recovery SOP.
- Do not expect printing to continue with the wrong cassette; v4 must keep the
  requests pending and identify required/detected media in the notice.

## Related SOPs

- `Failed_Batch_and_Print_Service_Recovery.md`
- `Print_Server_Runtime_Runbook.md`
- `Operator_Label_Printing.md`
- `../01_Engineering/Label_Service_v4_Architecture_and_Acceptance.md`
