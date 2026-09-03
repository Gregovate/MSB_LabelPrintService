# Controller Label Request and Physical Format Contract

| Document Control | Value |
|---|---|
| Document Type | Cross-repository integration contract |
| System | MSB Production Database / Controller Inventory / LabelPrintService |
| Status | PHYSICAL FORMAT AND SCAN ACCEPTED — spooler-observer hotfix awaiting deployment acceptance |
| Effective Date | 2026-09-03 |
| Controlling Issue | [LabelPrintService #18](https://github.com/Gregovate/MSB_LabelPrintService/issues/18) |
| Pull Requests | [LabelPrintService #22](https://github.com/Gregovate/MSB_LabelPrintService/pull/22), [#23](https://github.com/Gregovate/MSB_LabelPrintService/pull/23) |
| Controlled Candidate Version | `4.1.0-rc2` |

## Purpose

This document fixes the ownership boundary and exact data contract for permanent Controller ID labels. It prevents the existence of a database request flag, a working scan route, and a physical print consumer from being mistaken for the same completion state.

## Authoritative Controller Identity

The permanent identity is:

```text
CTRL:<controller_id>
```

`ref.controller.controller_id` is the only permanent Controller identity used for the label. Display assignments, network addresses, firmware, and other mutable Controller properties must not be encoded as identity.

## Deployed Request Contract

The MSB Production Database owns the request command and business-row mutation.

Deployed migration:

```text
Controllers/Database/022_create_controller_label_request_command.sql
```

Deployed command:

```sql
ref.request_controller_label(
    p_email text,
    p_controller_id bigint
)
```

The command:

- validates the active Directus user represented by `p_email`;
- requires the user to map to an active `ref.person` with the approved Controller capability;
- fails closed when identity or authorization cannot be established;
- grants the FieldWiring application execution of the command, not direct update access to `ref.controller`;
- sets only `ref.controller.print_label = true`;
- records request audit identity and time when the flag changes from false to true;
- is idempotent while the same Controller request is already pending.

LabelPrintService must consume `ref.controller.print_label`. It must not invent a second Controller request table or allow the browser to write the flag directly.

## Deployed Scan Contract

The Controller scan resolver is deployed and has accepted both forms:

```text
Printed/phone QR:
https://db.sheboyganlights.org/scan/CTRL/<controller_id>

Canonical compact identity / Zebra HID result:
CTRL:<controller_id>
```

Both resolve to Controller Inventory with the Controller selected:

```text
/fieldwiring/controllers?controller_id=<controller_id>
```

The full URL is the permanent physical QR payload. Zebra Advanced Data Formatting may shorten the scanned URL to the compact identity for HID workflows; it does not change what is printed.

## Approved Physical Label Contract

| Property | Contract |
|---|---|
| Printer | Brother PT-P950NW |
| Media | 24 mm laminated tape |
| Family | `QR_24MM_HORIZONTAL` |
| Template | `QR_label_1_line_horz_24mm.lbx` |
| `objLine1` | `CTRL:<controller_id>` |
| `objQr` | `https://db.sheboyganlights.org/scan/CTRL/<controller_id>` |
| Quantity | One permanent Controller ID label per governed request unless explicitly changed by a later accepted contract |

The existing V4 family preflight must reject missing, wrong-width, wrong-type, cover-open, printer-unavailable, or unsafe-queue states before an execution batch is created.

## LabelPrintService Consumer

The merged V4 service contains the Controller consumer:

- deterministic polling of pending `ref.controller.print_label` rows;
- validation that every pending Controller resolves to `QR_24MM_HORIZONTAL`;
- 24 mm laminated-media and one-line-template preflight;
- workload-signature verification before and after preflight;
- row locking and immutable Controller batch/item snapshot;
- direct b-PAC assignment to `objLine1` and `objQr`;
- one physical label per snapshotted Controller;
- targeted finalization that clears only the Controllers in the completed batch;
- cached print-count/time/requestor update;
- failed-batch persistence and repeat-print blocking.

Tracked SQL:

```text
sql/controller_snapshot_v4.sql
sql/controller_export.sql
sql/controller_finalized.sql
```

The consumer is guarded by `controller_polling_enabled`, which remains `false`
in the tracked example configuration. Production activation requires the local
configuration to set it to `true`. A failed preflight creates no execution
batch and leaves the request pending.

The first Controller-capable production candidate reported
`SERVICE_VERSION = "4.1.0-rc1"`. The spooler-observer correction advances the
controlled candidate to `4.1.0-rc2`. Promotion to `4.1.0` still requires
successful automatic finalization, restart, and no-double-print acceptance.

Production Database migration
`Controllers/Database/025_create_controller_label_print_batches.sql` was
merged through Production Database PR #120 at commit `f6683c5` and installed
on production PostgreSQL on 2026-09-03. Post-installation verification proved
all 177 Controllers use the 24 mm family, the new batch tables are empty, the
Controller audit trigger remains enabled, and the required `printservice`
table, column, and sequence permissions pass.

The V4 Scheduled Task and Controller consumer were installed and deliberately
enabled on PRINT-SERVER on 2026-09-03. The first controlled request produced
the correct `CTRL:1031` physical label. Phone scanning opened the full URL and
Controller 1031; Zebra HID returned `CTRL:1031`, appended Enter, and opened the
same Controller after the tablet scan field was manually focused.

That first physical print also exposed a completion defect. b-PAC returned
`PrintOut=True`, `EndPrint=True`, and `Close=True`, and the label physically
printed, but V4 did not begin Windows spooler observation until after all three
calls. The short one-label spooler row had already cleared, so batch 1 was
incorrectly marked `FAILED`. The service was stopped and batch 1 was reconciled
from physical and database evidence without reprinting.

Candidate `4.1.0-rc2` starts a shared high-frequency spooler observer before
`StartPrint`. It retains every new job ID even if the row clears before the
main thread reaches its completion check. It still fails when no new job is
ever observed or when an observed job remains stuck. The correction applies to
Display, Container, and Controller renderers.

Controller printing is not production-complete until `4.1.0-rc2` is deployed
and one controlled request proves automatic batch finalization, zero remaining
requests, restart safety, and no duplicate physical output.

## Pending-Request Safety Check

The production preflight immediately before migration 025 reported zero pending
Controller requests; Controller `1001` was not pending. Pending requests must
still be checked immediately before every controlled activation so enabling the
poller cannot unexpectedly print an old request.

## Cross-Repository Ownership

| Component | Owner |
|---|---|
| Controller record and `print_label` request | MSB Production Database |
| Authorized Controller browser action | Controller Inventory / FieldWiring |
| `/scan/CTRL/<id>` resolver | Production Database web application |
| Physical LBX, media preflight, rendering, batches, finalization | LabelPrintService |
| Zebra URL-to-`CTRL:` shortening | Scanner configuration |

## Completion Boundary

The Controller feature is not complete merely because the button queues the flag. It is complete only after the LabelPrintService consumer is implemented and the full request-to-physical-label path is accepted without premature database mutation or duplicate printing.
