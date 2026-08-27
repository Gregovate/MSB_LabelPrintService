# QR Payload and Label Profile Runtime Boundary

| Document control | Value |
|---|---|
| Status | DRAFT — ENGINEERING RECONNAISSANCE BASELINE |
| Revision | 2026-08-27 |
| Owner | MSB Label Print Service engineering |
| Related Production Database baseline | `e448f7b6fef8381522bd74e9c6ff1d9162ab8613` |
| LabelPrintService baseline | `d624420a1a7309fe12a608dd202b106bfe24ac9b` |

## Purpose

This document records the **LabelPrintService / PRINT-SERVER implementation boundary** for the reconciled MSB QR/payload and future label-profile architecture.

It must be read together with the Labeling and Scanning subsystem architecture maintained in `Gregovate/MSB-Production-Database-Project`.

The critical distinction is:

```text
Labeling and Scanning subsystem
    = owns/governs the cross-system label / payload / scan contract

MSB Production Database
    = owns authoritative database records and database implementation

MSB Label Print Service / PRINT-SERVER
    = owns physical printing and Brother/runtime implementation
```

The fact that Labeling and Scanning documentation currently lives inside the Production Database repository does **not** make Labeling and Scanning a Production Database subsystem implementation detail.

No production source, configuration, database schema, template, printer queue, or physical label was changed as part of this reconnaissance.

## Current Runtime Scope

Current `label_poll_service_v3.py` is Service Version 3.4 and processes production print requests for:

- Displays;
- Containers.

Current v3.4 does not have an accepted production Storage Location polling/batch/render path.

Rack/Location LBX files in this repository are experimental/template-design artifacts, not proof that Location printing is production-operational.

## Upstream Contract Boundary

LabelPrintService consumes two distinct upstream concerns:

### Labeling and Scanning contract

Labeling and Scanning governs:

- canonical label/payload conventions;
- compatibility requirements for deployed full-URL labels;
- logical QR/barcode requirements;
- logical label-profile requirements;
- scanner/input normalization expectations;
- whether a future label should encode a full URL, compact canonical payload, or another approved transport form.

LabelPrintService must not silently redefine those rules merely because the current URL happens to be constructed in service-owned SQL.

### Production Database implementation

The Production Database provides authoritative records and database-backed request/batch state such as:

- `display_id` and Display records;
- `container_id` and Container records;
- Storage Location keys/data where implemented;
- `print_label` request state;
- PostgreSQL batch/history/audit records;
- database relationships consumed by printing.

LabelPrintService consumes this database implementation but does not own the underlying business identity.

## Current QR Payload Origin

The renderer does not construct the semantic QR URL itself.

Display and Container snapshot SQL files owned by this repository construct the current full scan URL while the batch snapshot is created in PostgreSQL.

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

That duplicated SQL is a LabelPrintService implementation fact, not ownership of the canonical payload contract.

Any change from full URLs to compact canonical payloads must first be accepted as a Labeling and Scanning contract change.

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

This separation must be preserved. A future compact machine payload must not require changing visible label text merely because the QR content changes.

## Existing Physical Compatibility Constraint

Already-printed Display and Container labels contain full URLs such as:

```text
https://db.sheboyganlights.org/scan/DISP/323
https://db.sheboyganlights.org/scan/CONT/216
```

Those labels remain supported under the Labeling and Scanning compatibility contract and are not candidates for mass relabeling merely to improve Bluetooth HID speed.

LabelPrintService does not own scan-time compatibility rewriting for old labels. That belongs to the Labeling and Scanning input/Scan boundary.

This service controls only how an approved payload is physically rendered on future labels.

## Current Template/Printer Configuration

Current `config.example.ini` has one Windows printer name:

```text
Brother PT-P950NW
```

and explicit template paths for:

```text
display
container_vertical
container_horizontal
```

Current source loads those values into runtime constants and uses the single configured printer name for existing production jobs.

That design reflects the current production footprint but is not a scalable governed profile model.

## Template Source Layout Reconciliation

Issue #14 establishes the accepted source-layout direction as:

```text
templates/pt_p950nw/
templates/ql_820nwb/
```

Current history also contains temporary copies at other paths, including root-level template files and documentation/template copies.

Do not remove the temporary duplicates during QR/profile reconnaissance. Runtime paths, configuration, startup preflight, and controlled physical printing must prove the final source/runtime path before cleanup.

Template-design/test CSV files stored with template source are not the same thing as production runtime-generated CSV exports.

## Issue #14 / Draft PR #15 Boundary

Issue #14 exists because v3.4 could create and commit a batch before discovering that a configured runtime CSV parent directory was missing.

The existing FAILED-batch guard correctly stopped an automatic reprint storm, but the batch should not have been created when required runtime paths were invalid.

Draft PR #15 remains work-in-progress for that issue.

Future profile work must extend, not bypass, the final preflight model. A logical profile that selects another printer/template/media/image renderer must participate in the same before-batch validation boundary.

## Governed Label Profile — Runtime Role Only

The logical label-profile contract belongs to the Labeling and Scanning subsystem.

If the Production Database implements that contract as a governed PostgreSQL entity such as a future `ref.label_profile`, that table remains a Production Database implementation of the Labeling and Scanning contract.

LabelPrintService should consume the resolved logical profile identity and map it to runtime details.

Conceptual mapping:

```text
Labeling and Scanning logical profile
    -> Production Database stores/resolves approved profile assignment
        -> LabelPrintService receives effective profile
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

Windows printer names and absolute template paths remain service/runtime configuration. They must not be copied into `ref.display` or other Production Database asset rows.

Likewise, this service's configuration must not become the only authority for which logical profile an asset or workflow requires.

## Profile Snapshot Requirement

When a governed profile is implemented, the batch should carry the resolved logical profile identity and actual human/machine values to print.

The service should not re-resolve an asset's current default profile after the batch has been created. That would violate the snapshot-batch design.

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

Brother b-PAC documentation supports application replacement of an image object. Brother documents `IObject::SetData()` for b-PAC 3.x and the older `ReplaceImageFile()` equivalent; BMP is among supported image formats in older SDK documentation.

Once an approved Labeling and Scanning profile calls for raster QR rendering, this service may implement:

```text
approved payload
    -> LabelPrintService QR encoder
    -> explicit QR version / ECC / quiet zone
    -> monochrome lossless raster image
    -> named LBX image object
    -> b-PAC image replacement
    -> physical printer
```

This is technically feasible but not production-proven on PRINT-SERVER.

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

Prefer a lossless raster format such as BMP for the first proof.

## QR Density Consequence

The current example full URL is 44 ASCII bytes:

```text
https://db.sheboyganlights.org/scan/DISP/323
```

Minimum QR versions are:

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

The service must not hard-code a QR version independently of the approved Labeling and Scanning profile/payload contract. A raster renderer may deliberately implement the accepted version/ECC after physical testing.

## Current Documentation Drift

Material drift includes:

- root `readme.md` records an older production/main baseline even though actual repository `main` is now `d624420a1a7309fe12a608dd202b106bfe24ac9b`;
- `docs/01_Engineering/How_Label_Service_Works.md` contains historical manual-start/office-workstation statements superseded by accepted PRINT-SERVER unattended runtime;
- template copies exist at multiple paths while Issue #14 defines the intended printer-specific source layout;
- experimental QL/rack templates must not be described as production Location printing;
- earlier QR/profile wording incorrectly collapsed the Labeling and Scanning subsystem into the Production Database repository boundary. This document now explicitly preserves the separation.

These documents remain useful evidence. Reconcile them deliberately; do not delete them merely because portions are stale.

## Implementation Gates

Before modifying v3.4 for label profiles or raster QR:

1. Reconcile from then-current LabelPrintService `main`.
2. Read the current Labeling and Scanning subsystem boundary/architecture in `MSB-Production-Database-Project`.
3. Confirm the proposed change is actually a LabelPrintService implementation change rather than an unapproved Labeling and Scanning contract change.
4. Complete and accept Issue #14 runtime preflight hardening, or explicitly integrate the final accepted preflight contract into the profile work.
5. Verify actual production `config.local.ini` and template paths without exposing secrets.
6. Verify installed b-PAC version on PRINT-SERVER.
7. Verify the logical profile/payload contract has been accepted by Labeling and Scanning.
8. Build raster QR work as an isolated template/test path first.
9. Verify both old full-URL scans and any new compact payload end to end through the Labeling and Scanning acceptance path.
10. Verify exact printer/media selection before batch creation.
11. Run controlled physical print acceptance with exactly-once expectations.
12. Preserve all current FAILED-batch and no-double-print protections.

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
- [Labeling and Scanning subsystem architecture](https://github.com/Gregovate/MSB-Production-Database-Project/tree/main/Docs/02_Production_Database/01_System_Architecture/07_Labeling_and_Scanning)
