# MSB Label Print Service — Engineering Documentation

- [V4 Controlled Production Deployment and Queue Plan — 2026-09-03](V4_Controlled_Deployment_and_Queue_Plan_2026-09-03.md) — active cutover evidence, silent polling/job-table contract, missing request pipelines, and low-tape investigation.

| Document Control | Value |
|---|---|
| Document Type | README / Engineering Documentation Portal |
| System | MSB Label Print Service / PRINT-SERVER |
| Status | CURRENT |
| Last Reviewed | 2026-09-02 |

Engineering architecture, implementation contracts, acceptance requirements, and known technical limitations belong in this folder. Operational procedures belong under `docs/02_Operational_SOPs/`.

## Current / Active Engineering Work

- [Label Service v4 — Architecture and Acceptance Contract](Label_Service_v4_Architecture_and_Acceptance.md) — authoritative v4 design record for logical label families, physical templates, printer/media mapping, fail-safe preflight, operator dialogs, tape-out instrumentation/recovery, batch-family rules, and controlled acceptance. Payload sections are superseded where explicitly stated by the 2026-09-02 QR payload decision below.
- [Brother SNMP Status Evidence](Brother_SNMP_Status_Evidence.md) — tracked raw PT-P950NW and QL-820NWB SNMP/status packets for ready, wrong-media-relevant widths, no-media, cover-open, and P950 tape-out conditions; also records untested and invalid probe cases.
- [12 mm Wiring Field-Data Evidence](Wiring_12mm_Field_Data_Evidence.md) — source SQL, recovered 50-row longest production `channel_name` result, real split-label fixtures, two-digit channel formatting rule, and acceptance-use boundary.
- [QR Payload and Zebra ADF Decision — 2026-09-02](QR_Payload_and_Zebra_ADF_Decision_2026-09-02.md) — current accepted payload contract: V4 Display and Container QR codes retain the exact v3 full scan URLs; Zebra ADF shortens those URLs to `DISP:` / `CONT:` during scanner HID transmission.
- [Container QR Physical Acceptance — 2026-09-01](Container_QR_Physical_Acceptance_2026-09-01.md) — controlled physical-print evidence for QR Version 4 / 15% error correction and two-label Container output. Its earlier compact physical-payload direction is superseded by the 2026-09-02 QR payload decision.
- [How Label Service Works](How_Label_Service_Works.md) — v3.x production architecture/background. Retain as the current-production baseline until v4 is accepted and deployed.
- [Label Service TODO](TODO_Label_Service.md) — older engineering TODO record; review against the v4 contract before acting on stale items.

## Documentation Rule

Accepted architecture or operational behavior must be written into repository documentation as part of the change. GitHub issues and chat discussions may record investigation/evidence, but they are not the sole authority for deployed behavior.
