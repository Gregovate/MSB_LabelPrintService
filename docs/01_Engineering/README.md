# MSB Label Print Service — Engineering Documentation

| Document Control | Value |
|---|---|
| Document Type | README / Engineering Documentation Portal |
| System | MSB Label Print Service / PRINT-SERVER |
| Status | CURRENT |
| Last Reviewed | 2026-08-31 |

Engineering architecture, implementation contracts, acceptance requirements, and known technical limitations belong in this folder. Operational procedures belong under `docs/02_Operational_SOPs/`.

## Current / Active Engineering Work

- [Label Service v4 — Architecture and Acceptance Contract](Label_Service_v4_Architecture_and_Acceptance.md) — authoritative v4 design record for logical label families, physical templates, printer/media mapping, fail-safe preflight, operator dialogs, tape-out instrumentation/recovery, batch-family rules, and controlled acceptance.
- [How Label Service Works](How_Label_Service_Works.md) — v3.x production architecture/background. Retain as the current-production baseline until v4 is accepted and deployed.
- [Label Service TODO](TODO_Label_Service.md) — older engineering TODO record; review against the v4 contract before acting on stale items.

## Documentation Rule

Accepted architecture or operational behavior must be written into repository documentation as part of the change. GitHub issues and chat discussions may record investigation/evidence, but they are not the sole authority for deployed behavior.
