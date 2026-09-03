# QR Payload and Zebra ADF Decision — 2026-09-02

| Document Control | Value |
|---|---|
| Status | CURRENT ACCEPTED DECISION |
| System | MSB Label Print Service / Zebra scanning compatibility |
| Branch | `agent/runtime-preflight-hardening` |
| Related Issue | LabelPrintService #14 / Production Database #88 |
| Date | 2026-09-02 |

## Purpose

This document records the final payload decision reached after controlled Zebra DS3678 scanner acceptance. It supersedes the earlier v4 Container compact-payload direction recorded in `Label_Service_v4_Architecture_and_Acceptance.md` and `Container_QR_Physical_Acceptance_2026-09-01.md` wherever those documents say that newly printed v4 Container QR codes should contain `CONT:<id>`.

The physical QR code and the scanner-transmitted value are now intentionally separate concerns.

## Permanent physical QR payload contract

V4 must preserve the exact v3 full scan URL for both Display and Container QR labels.

```text
Display:
https://db.sheboyganlights.org/scan/DISP/<display_id>

Container:
https://db.sheboyganlights.org/scan/CONT/<container_id>
```

Examples:

```text
https://db.sheboyganlights.org/scan/DISP/323
https://db.sheboyganlights.org/scan/CONT/216
```

This keeps newly printed/replacement labels compatible with the thousands of labels already deployed and preserves direct phone-camera behavior: a phone can scan the QR and open the URL without requiring the MSB scanner workflow.

## Zebra scanner ADF owns shortening

The DS3678 scanners are configured with Advanced Data Formatting rules that recognize the established long URL format and shorten the data before HID transmission to the tablet.

Conceptually:

```text
physical Display QR
https://db.sheboyganlights.org/scan/DISP/323
    -> Zebra ADF
DISP:323
    -> carriage return

physical Container QR
https://db.sheboyganlights.org/scan/CONT/216
    -> Zebra ADF
CONT:216
    -> carriage return
```

This removes Bluetooth keyboard latency without changing the physical QR payload.

The scanner rule depends on the exact historical URL structure. Therefore LabelPrintService must not change the protocol, hostname, `/scan/` path, `DISP`/`CONT` descriptor, slash placement, or capitalization without a separately controlled compatibility change to the scanner configuration.

## V4 implementation consequence

`sql/display_snapshot_v4.sql` already retained the exact v3 Display URL and requires no payload change.

`sql/container_snapshot_v4.sql` is restored to the exact v3 Container URL:

```sql
'https://db.sheboyganlights.org/scan/CONT/' || c.container_id AS qr_url
```

The `qr_url` batch field again contains a literal URL for both Display and Container identity labels.

## Location labels remain different

Rack/Location labels use Code 128 and already contain the compact canonical value:

```text
LOC:<location_code>
```

They do not require URL removal. The scanner rule for Location only needs to preserve the existing `LOC:` payload and append carriage return for one-trigger submission.

## Scanner acceptance findings that drive this decision

- The DS3678 ER scanner is suitable for workshop scanning.
- Full URLs decode quickly but are slow when transmitted as Bluetooth keyboard characters.
- Zebra ADF successfully converts the exact deployed Display and Container URL patterns to compact `DISP:` and `CONT:` values before tablet delivery.
- This allows existing and newly printed full-URL QR labels to work well with both phone cameras and Zebra scanners.
- Glossy laminated label stock materially reduces reliable off-axis scan angle; a more face-on presentation is required than with larger matte Code 128 labels.

## Guardrail

Do not reintroduce compact `CONT:<id>` or `DISP:<id>` as the physical QR payload merely to optimize scanner transmission. Scanner-side ADF now provides that optimization while preserving the established physical-label contract.
