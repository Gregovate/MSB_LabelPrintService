# Controller Label Request and Physical Format Contract

| Document Control | Value |
|---|---|
| Document Type | Cross-repository integration contract |
| System | MSB Production Database / Controller Inventory / LabelPrintService |
| Status | CURRENT — upstream request and scan contracts deployed; physical consumer pending |
| Effective Date | 2026-09-03 |
| Controlling Issue | [LabelPrintService #14](https://github.com/Gregovate/MSB_LabelPrintService/issues/14) |
| Pull Request | [LabelPrintService #15](https://github.com/Gregovate/MSB_LabelPrintService/pull/15) |

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

## LabelPrintService Consumer — Not Yet Implemented

The upstream request and scan route are complete. V4 still needs:

1. deterministic polling of pending `ref.controller.print_label` rows;
2. 24 mm family selection and full preflight;
3. immutable Controller batch header/item snapshot;
4. b-PAC rendering through the approved object contract;
5. one-label-at-a-time execution evidence;
6. targeted success finalization that clears only the snapshotted requests actually printed;
7. restart, failure, and no-double-print behavior;
8. controlled physical acceptance from the deployed Scheduled Task context.

A failed preflight must create no execution batch and leave the request pending.

## Pending-Request Safety Check

A previously documented accidental request for Controller `1001` may still be pending. Before the new consumer is enabled, inspect and deliberately clear or intentionally test that request. Enabling the poller must not unexpectedly print an old request.

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
