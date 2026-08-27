# QR Payload and Label Profile Runtime Boundary

| Document control | Value |
|---|---|
| Status | DRAFT — ENGINEERING RECONNAISSANCE BASELINE |
| Revision | 2026-08-27 |
| Owner | MSB Label Print Service engineering |
| Related Production Database baseline | `e448f7b6fef8381522bd74e9c6ff1d9162ab8613` |
| LabelPrintService baseline | `d624420a1a7309fe12a608dd202b106bfe24ac9b` |

## Purpose

This document records the LabelPrintService side of the reconciled MSB QR/payload and future label-profile architecture.

It is intentionally a runtime boundary document. Durable asset identity and governed label-profile assignment belong to `Gregovate/MSB-Production-Database-Project`.

No production source, configuration, database schema, template, printer queue, or physical label was changed as part of this reconnaissance.

## Current Runtime Scope

Current `label_poll_service_v3.py` is Service Version 3.4 and processes production print requests for:

- Displays;
- Containers.

Current v3.4 does **not** have an accepted production Storage Location polling/batch/render path.

Rack/Location LBX files under the repository are experimental/template-design artifacts, not proof that Location printing is production-operational.

## Current QR Payload Origin

The renderer does not construct the semantic QR URL itself.

Display and Container snapshot SQL files construct the current full scan URL while the batch snapshot is created in PostgreSQL.

### Display

`sql/display_snapshot.sql` writes:

```sql
'https://db.sheboyganlights.org/scan/DISP/' || d.display_id AS qr_url
```

The value is stored in `ops.display_label_batch_item.qr_url` and later exported to the service.

### Container

`sql/container_snapshot.sql` writes:

```sql
'https://db.sheboyganlights.org/scan/CONT/' || c.container_id AS qr_url
```

The value is stored in `ops.container_label_batch_item.qr_url` and later exported to the service.

There is no shared QR/payload helper in current v3.4; Display and Container snapshot SQL duplicate the URL convention.

## Current b-PAC Object Contract

Current Display templates are expected to expose:

```text
objLine1
objLine2   (optional in current code)
objQr
```

Current Container templates are expected to expose:

```text
objContainerLabel
objQr
```

The renderer assigns human text and machine-readable content independently.

Display:

```text
objLine1.Text <- row.line1
objLine2.Text <- row.line2
objQr.Text    <- row.qr_url
```

Container:

```text
objContainerLabel.Text <- row.container_label
objQr.Text              <- row.qr_url
```

This separation must be preserved. A future compact machine payload must not require changing the visible label text merely because the QR content changes.

## Existing Physical Compatibility Constraint

Already-printed Display and Container labels contain full URLs such as:

```text
https://db.sheboyganlights.org/scan/DISP/323
https://db.sheboyganlights.org/scan/CONT/216
```

Those physical labels remain supported by the Production Database Scan application and are not candidates for mass relabeling merely to improve Bluetooth HID speed.

The LabelPrintService should not own a compatibility rewrite for scanned old labels; that belongs at the scan/input boundary. The print service only controls what is encoded on labels it prints in the future.

## Current Template/Printer Configuration

Current `config.example.ini` has one Windows printer name:

```text
Brother PT-P950NW
```

and three explicit template paths:

```text
display
container_vertical
container_horizontal
```

Current source loads those values into separate runtime constants and uses the single printer name for all production jobs.

That design reflects the current production footprint but is not a scalable governed profile model.

## Template Source Layout Reconciliation

Issue #14 establishes the accepted source-layout direction as:

```text
templates/pt_p950nw/
templates/ql_820nwb/
```

Current repository history also contains temporary copies at other paths, including root-level template files and documentation/template copies.

Several duplicates are byte-identical in Git history.

Do **not** remove the temporary duplicates during QR/profile reconnaissance. Runtime paths, configuration, startup preflight, and controlled physical printing must prove the final source/runtime path before cleanup.

Template-design/test CSV files stored with template source are not the same thing as production runtime-generated CSV exports.

## Issue #14 / Draft PR #15 Boundary

Issue #14 exists because v3.4 could create and commit a batch before discovering that a configured runtime CSV parent directory was missing.

The existing FAILED-batch guard correctly stopped an automatic reprint storm, but the batch should not have been created when required runtime paths were invalid.

Draft PR #15 is current work-in-progress for that issue. It must remain separate from QR/profile architecture until its runtime preflight/write-path changes and controlled acceptance tests are complete.

Future profile work must extend, not bypass, the final preflight model. A profile that selects another printer/template/media/image renderer must participate in the same before-batch validation boundary.

## Proposed Runtime Role for Governed Label Profiles

The Production Database may later define a governed logical label-profile entity. The exact schema is not owned here.

LabelPrintService should consume a stable logical profile identity and map it to runtime details.

Conceptual mapping:

```text
logical label profile
    -> printer capability role
    -> local Windows printer queue
    -> LBX template
    -> media requirement
    -> renderer type
    -> required template object contract
```

Examples of capability classes, not approved profile keys:

- current 36 mm PT-P950NW Display label;
- future narrower PT-P950NW Display label;
- future 12 mm PT-P950NW FieldWiring label;
- future large QL-820NWB Location/rack label.

Windows printer names and absolute template paths remain service/runtime configuration. They should not be copied into `ref.display` or other Production Database asset rows.

## Profile Snapshot Requirement

When a governed profile is implemented, the batch should carry the resolved logical profile identity and the actual human/machine values to print.

The service should not re-resolve an asset's current default profile after the batch has been created. That would violate the current snapshot-batch design.

Any profile extension must preserve:

- deterministic batch contents;
- FAILED-batch persistence;
- no automatic double print;
- queue-empty guard;
- spooler verification;
- controlled retry/recovery.

## Native QR Versus Raster QR

Current production templates use a native Brother QR object and set `objQr.Text`.

For future large-distance labels, Brother Editor behavior may make the native object unsuitable when increasing physical size also increases QR version/density.

Brother b-PAC documentation supports application replacement of an image object. Brother documents `IObject::SetData()` for b-PAC 3.x and the older `ReplaceImageFile()` equivalent; BMP is among supported image formats in the older SDK specification.

This supports an additive renderer concept:

```text
payload
    -> software QR encoder
    -> explicit QR version / ECC / quiet zone
    -> monochrome BMP
    -> named LBX image object
    -> b-PAC image replacement
    -> printer
```

Reference:

- https://support.brother.com/g/s/es/dev/en/bpac/faq/index.html

This is technically feasible but **not production-proven on PRINT-SERVER**.

Before implementation, verify:

- exact installed b-PAC version;
- Python COM method signature for image replacement;
- image-object behavior on the intended LBX template;
- actual PT-P950NW/QL-820NWB driver behavior;
- raster DPI and integer module scaling;
- quiet zone;
- media/preflight behavior;
- temporary image creation and cleanup;
- spooler and FAILED-batch behavior on image-generation/render failure.

Prefer a lossless raster format such as BMP for the first proof because it is explicitly documented by older b-PAC specifications and avoids compression artifacts in QR edges.

## QR Density Consequence

The current example full URL is 44 ASCII bytes:

```text
https://db.sheboyganlights.org/scan/DISP/323
```

The minimum QR versions are:

| ECC | Minimum version |
|---|---:|
| L | 3 |
| M | 4 |
| Q | 4 |
| H | 5 |

Version 2 cannot hold the current full URL at any ECC level.

Compact canonical examples are materially smaller:

```text
DISP:323 -> Version 1 even at H
CONT:216 -> Version 1 even at H
LOC:RB07-B-01 -> Version 1 at L/M/Q; Version 2 at H
```

QR capacity and quiet-zone references:

- https://www.qrcode.com/en/about/version.html
- https://www.qrcode.com/en/howto/code.html

The runtime should not hard-code a QR version independently of the governed profile/payload contract. A raster profile can deliberately specify the accepted version/ECC after physical testing.

## Current Documentation Drift

The following drift is material:

- root `readme.md` still records an older production/main baseline even though actual repository `main` is now `d624420a1a7309fe12a608dd202b106bfe24ac9b`;
- `docs/01_Engineering/How_Label_Service_Works.md` contains historical manual-start/office-workstation statements superseded by the accepted PRINT-SERVER unattended runtime;
- current template copies exist at multiple paths while Issue #14 defines the intended printer-specific source layout;
- experimental QL/rack templates should not be described as production Location printing.

These documents remain useful evidence. Reconcile them deliberately; do not delete them merely because portions are stale.

## Implementation Gates

Before modifying v3.4 for label profiles or raster QR:

1. Rebase/reconcile from then-current `main`.
2. Complete and accept Issue #14 runtime preflight hardening, or explicitly integrate the final accepted preflight contract into the profile work.
3. Verify actual production `config.local.ini` and template paths without exposing secrets.
4. Verify installed b-PAC version on PRINT-SERVER.
5. Verify the logical profile contract approved in the Production Database repository.
6. Build any raster QR work as an isolated template/test path first.
7. Verify both old full-URL scans and any new compact payload end to end.
8. Verify exact printer/media selection before batch creation.
9. Run controlled physical print acceptance with exactly-once expectations.
10. Preserve all current FAILED-batch and no-double-print protections.

## Current Stop Point

Architecture is documented; implementation has not started.

No executable source, production configuration, LBX template, printer, database object, batch safety rule, or physical label was changed by this work.

## Related Systems

- [MSB Production Database Project](https://github.com/Gregovate/MSB-Production-Database-Project)
- [Issue #14 — runtime preflight hardening](https://github.com/Gregovate/MSB_LabelPrintService/issues/14)
- [Draft PR #15 — runtime preflight hardening](https://github.com/Gregovate/MSB_LabelPrintService/pull/15)

## Related Documents

- [How the Label Service Works](How_Label_Service_Works.md)
- [Label Print Service Engineering Rules](../../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
- [Print Server Runtime Runbook](../02_Operational_SOPs/Print_Server_Runtime_Runbook.md)
