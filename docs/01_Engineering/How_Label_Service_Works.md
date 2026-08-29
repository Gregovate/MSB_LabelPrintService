# MSB Label Printing System — How It Works

| Document control | Value |
|---|---|
| Status | CURRENT ENGINEERING BASELINE — SETUP HARDENING IN PROGRESS |
| Revision | 2026-08-28 |
| System | MSB Label Print Service |
| Current production service | v3.4 |
| Owner | MSB Label Print Service / PRINT-SERVER engineering |

## Purpose

This document explains the current architecture and runtime behavior of the MSB Label Printing System and records the bounded Setup-hardening changes now under engineering review.

It is intended for administrators, developers, and future maintainers. The physical PRINT-SERVER deployment/startup/recovery procedure is owned by [`Print_Server_Runtime_Runbook.md`](../02_Operational_SOPs/Print_Server_Runtime_Runbook.md).

## Current Production Scope

Current production v3.4 prints:

- Display labels; and
- Container labels.

Storage Location/rack printing is not yet a production capability. QL-820NWB testing, final Location media/layout, paper-out/readiness behavior, and accepted Location scan workflow remain pending.

## System Components

### 1. Directus — current request interface

Operators currently:

1. search/filter Display or Container rows;
2. select one or many records;
3. enable **Print Label**; and
4. save.

This sets:

```text
ref.display.print_label = true
```

or:

```text
ref.container.print_label = true
```

No printing occurs inside Directus. There is no database trigger that starts printing.

### 2. PostgreSQL Production Database

PostgreSQL is authoritative for Display/Container identity and current print-request/batch state.

Current source tables:

```text
ref.display
ref.container
```

Current batch tables:

```text
ops.display_label_batch
ops.display_label_batch_item
ops.container_label_batch
ops.container_label_batch_item
```

Snapshot batching preserves the selected print set and prevents source-record changes from silently changing an already-created batch.

### 3. Label Polling Service

Current production script:

```text
C:\MSB_LabelService\label_poll_service_v3.py
```

Current service version:

```text
3.4
```

The production service runs on the dedicated Beelink host:

```text
PRINT-SERVER
C:\MSB_LabelService
```

It is started automatically by the Windows Scheduled Task **MSB Label Service**. Manual desktop startup is no longer the normal operating model.

The service polls PostgreSQL every 15 seconds and currently performs:

- pending Display/Container detection;
- active/FAILED batch guards;
- current printer/template preflight;
- snapshot batch creation;
- CSV generation;
- Brother b-PAC rendering/submission;
- Windows spooler verification;
- batch finalization; and
- clearing only the snapshot rows that successfully complete.

### 4. Brother PT-P950NW

The currently accepted production printer for laminated Display and Container labels is:

```text
Brother PT-P950NW
```

Printing uses Brother b-PAC and `.lbx` templates.

A QL-820NWB is available for future non-laminated/QL-media work, but it is not yet part of accepted production Location printing.

## Current Runtime Paths

Canonical local service root:

```text
C:\MSB_LabelService
```

Current template root:

```text
C:\MSB_LabelService\templates
```

The intended final template organization is:

```text
C:\MSB_LabelService\templates\
    pt_p950nw\
    ql_820nwb\
```

Root-level template copies currently remain during transition because deployed v3.4 still uses explicit paths from `config.local.ini`.

The network share `\\print-server\MSB_LabelService` is an administrative view of the same local deployment; the service should use local `C:` paths.

See the PRINT-SERVER runtime runbook for the controlled path/configuration contract.

## Current Configuration Model

v3.4 loads template paths from `config.local.ini`; the `.lbx` paths are not literal constants embedded in the Python source.

The current limitation is the **shape** of the configuration/code: it assumes one global Display template, one Container vertical template, one Container horizontal template, and one global printer name.

Conceptually the current code resolves:

```text
DISPLAY_TEMPLATE
CONTAINER_VERTICAL_TEMPLATE
CONTAINER_HORIZONTAL_TEMPLATE
PRINTER_NAME
```

That cannot distinguish a 24 mm Display from a 36 mm Display or choose among multiple runtime printer/template implementations.

## End-to-End Current Workflow

```text
Directus
    -> print_label = true

LabelPrintService poll
    -> count pending Display/Container rows
    -> block if active PRINTING or unresolved FAILED batch exists
    -> current printer/template preflight
    -> ensure Windows queue is empty
    -> create snapshot batch
    -> COMMIT batch header/items
    -> export batch rows / write CSV
    -> open LBX through b-PAC
    -> set printer
    -> populate objects
    -> PrintOut loop
    -> wait for spooler job to appear and clear
    -> finalize batch
    -> clear only included print_label flags
```

## Important Current Preflight Gap

The current preflight is **not complete enough**.

A production failure on 2026-08-27 proved the current sequence can:

```text
printer/template preflight passes
    -> batch is created and committed
        -> process_display writes runtime CSV
            -> missing CSV directory/path fails
                -> committed batch becomes FAILED
                    -> manual database recovery is required before retry
```

The current `write_csv()` path is therefore downstream of committed batch creation.

Setup hardening must change the safety boundary to:

> **Every deterministic prerequisite required for the compatible pending workload must pass before any execution batch header/items are created.**

Required preflight includes at least:

- required SQL files readable;
- runtime CSV/output paths available/writable;
- selected template exists;
- b-PAC can open the selected template;
- required template objects exist;
- required Windows printer can be selected;
- correct usable media is loaded;
- queue is safe/empty;
- required state/log/runtime directories are valid; and
- no active/FAILED work blocks safe execution.

`write_csv()` should still defensively ensure its parent exists immediately before writing as race protection.

## Display Label Sizes — Setup Requirement

Setup requires two Display identity formats:

```text
36 mm laminated — current standard
24 mm laminated — narrow Display format
```

The current service cannot distinguish these because every pending Display uses the same global `DISPLAY_TEMPLATE`.

The Production Database branch contains a reviewed candidate for a new lookup:

```text
ref.label_template
```

with initial codes:

```text
DISPLAY_36MM
DISPLAY_24MM
```

The eventual relationship from `ref.display` is not implemented yet. Before modifying that existing production table, engineering must inspect the live `ref.display` schema, triggers, grants, dependencies, and Directus metadata.

Existing Displays are intended to default/backfill to 36 mm; selected Displays can then be deliberately changed to 24 mm.

## Template Lookup Direction

The accepted Setup direction separates the machine-local root from the governed relative template path.

Example:

```text
PRINT-SERVER config.local.ini:
    template_dir = C:\MSB_LabelService\templates

PostgreSQL:
    template_relative_path = pt_p950nw/QR_display_labels_2_line_24mm.lbx

Resolved at runtime:
    C:\MSB_LabelService\templates\pt_p950nw\QR_display_labels_2_line_24mm.lbx
```

This allows a template location/assignment change without editing Python source while still allowing the entire service installation root to move through one machine-local configuration change.

Operators do not choose Windows printers or `.lbx` paths. They select/request the required label format; LabelPrintService resolves the physical implementation and preflight.

## Mixed Pending Display Variants

Keeping the existing boolean workflow means 24 mm and 36 mm Displays could be flagged at the same time.

The revised service must resolve/group pending Displays by effective compatible template/media **before batch creation**.

One execution batch may contain only one compatible runtime printer/template/media requirement.

The service must never:

- snapshot 24 mm and 36 mm Displays into the same batch;
- clear `print_label` for a Display that was not included in the completed compatible batch; or
- create a FAILED cleanup condition merely because incompatible pending requests coexist.

## Current QR Payload and Setup Direction

Current `sql/display_snapshot.sql` constructs:

```text
https://db.sheboyganlights.org/scan/DISP/<display_id>
```

and the Container snapshot path similarly constructs a full `/scan/CONT/<container_id>` URL.

Existing printed full-URL labels remain supported physical artifacts.

Current Scan input also accepts compact canonical tokens:

```text
DISP:<display_id>
CONT:<container_id>
```

Bluetooth HID testing showed that typing the full URL into Android takes materially longer than the compact token. New/replacement compact QR payloads are therefore part of Setup-hardening acceptance, but must not be documented as production behavior until regression and physical scanner testing pass.

## b-PAC Rendering

Current Display template object names:

```text
objLine1
objLine2   optional in code
objQr
```

Current Container object names:

```text
objContainerLabel
objQr
```

The service populates those objects and calls b-PAC `PrintOut()`.

b-PAC submission success is not treated by itself as proof that the physical label printed.

## Windows Spooler Verification

After submission, the service watches the Windows print queue.

The current accepted overall-job success evidence is:

- a new relevant spooler job appears; and
- that job clears within the allowed timeout.

This protects against several silent submission failures, but it does **not** prove per-label physical completion inside a multi-label b-PAC session.

Do not report item-level labels as physically printed unless later engineering creates evidence that supports that claim.

## Container Quantity Behavior

Displays print one physical label per selected Display.

Containers currently print two physical labels per selected Container. The service duplicates each Container row in memory before rendering.

The database currently stores one logical Container batch item, not two independently checkpointed physical instances.

## Failure / Duplicate-Prevention Model

Current safety features include:

- one active PRINTING batch guard;
- unresolved FAILED batch guard;
- queue-empty check before batch creation;
- snapshot batching;
- batch commit before physical printing so post-batch failures remain visible;
- leaving source `print_label` flags set on failure; and
- no blind automatic retry of unresolved FAILED batches.

Setup preflight hardening must preserve those protections while preventing known deterministic failures from creating a batch in the first place.

## PRINT-SERVER Status UI — Accepted Design, Not Yet Deployed

The current unattended service gives normal users almost no local feedback when a label is blocked by a physical condition.

The accepted Setup direction is one singleton tray/status UI:

```text
normal / successful operation
    -> tray only
    -> no per-job windows
    -> no routine popup

action required
    -> show/restore the same one status window
    -> explain the condition in operator terms
       e.g. "24 mm laminated tape required; 36 mm loaded"

condition corrected
    -> service safely re-evaluates
    -> printing may continue automatically
    -> status returns to tray
```

Closing the visible status window must hide the UI, not stop the print engine.

The print engine must continue to auto-start through the Scheduled Task. A normal-user manual **Start Print Server** shortcut/button is not part of the accepted workflow.

This UI is pending implementation and physical PRINT-SERVER acceptance. Do not describe it as production deployed yet.

## Startup / Singleton Protection

The production Scheduled Task is configured so that if the task is already running, Windows does not start a new instance.

Future Setup hardening should retain that host-level protection and add application-level single-instance protection where practical, particularly because the previous manual-start workflow encouraged users to start the service again when a print was delayed.

## Engineering / Repository Boundary

### Production Database

Owns:

- authoritative asset data;
- current print request flags and batch/history objects;
- governed `ref.label_template` implementation when deployed;
- eventual Display relationship after live-schema review.

### LabelPrintService

Owns:

- Python service/runtime;
- `C:\MSB_LabelService` deployment;
- machine-local `config.local.ini`;
- Brother templates;
- Windows printer queues;
- template-root/printer runtime mapping;
- b-PAC;
- complete physical/runtime preflight;
- tray/status implementation;
- spooler/recovery behavior.

### Labeling and Scanning

Owns the cross-system label/payload/scan contract, including compatibility of old full-URL labels and accepted compact payload direction.

## Current Acceptance Boundary

Current production v3.4 remains the accepted runtime until the Setup-hardening branch passes controlled onsite tests.

Remote repository work may prepare:

- template lookup/configuration;
- complete preflight ordering;
- non-hardware tests;
- documentation;
- tray/status implementation candidate; and
- database integration scripts.

Onsite acceptance is still required for:

- 24 mm and 36 mm physical Display printing;
- actual loaded-media detection;
- b-PAC printer/template switching;
- exception/status-window behavior on the Beelink desktop;
- physical QR/scanner behavior; and
- any QL-820NWB readiness/media-out behavior.

## Related Documentation

- [PRINT-SERVER Runtime Runbook](../02_Operational_SOPs/Print_Server_Runtime_Runbook.md)
- [Failed Batch and Print Service Recovery](../02_Operational_SOPs/Failed_Batch_and_Print_Service_Recovery.md)
- [Operator Label Printing](../02_Operational_SOPs/Operator_Label_Printing.md)
- Production Database Labeling and Scanning engineering documentation
- LabelPrintService Issue #14

## Revision History

| Date | Change |
|---|---|
| 2026-08-28 | Reconciled the document with dedicated PRINT-SERVER Scheduled Task operation, current v3.4 execution order, incomplete preflight boundary, 24/36 mm Display requirement, relative template lookup, mixed-media grouping requirement, compact-QR acceptance direction, and planned tray-only normal status UX. |
| 2026-04-16 | v3.4 rotating log and explicit pre-print batch-commit logging baseline. |
| 2026-03-30 | v3.2 requester actor attribution. |
| 2026-03-26 | v3.1 failed-batch guard / no automatic retry. |
| 2026-03-21 | v3.0 queue-verified printing architecture. |
