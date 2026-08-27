# Label Print Service Engineering

Engineering documentation for the MSB Label Print Service / PRINT-SERVER runtime.

## System Boundary

This repository is **not** the Labeling and Scanning subsystem and is **not** the MSB Production Database repository.

Keep the three boundaries separate:

```text
Labeling and Scanning subsystem
    = cross-system label / payload / scan contract

MSB Production Database
    = authoritative database records and database implementation

MSB Label Print Service / PRINT-SERVER
    = physical printing and Brother/runtime implementation
```

This repository consumes the approved Labeling and Scanning contract and Production Database request/batch state. It owns Brother templates, b-PAC, printer/media mapping, spooler verification, runtime paths, service safety behavior, and PRINT-SERVER recovery. It does not own canonical asset identity, scan business routing, or a competing logical label-profile authority.

## Current Engineering References

- [QR Payload and Label Profile Runtime Boundary](QR_Payload_and_Label_Profile_Runtime_Boundary.md) — current 2026-08-27 reconnaissance baseline for QR payload origin, cross-system responsibility, template/profile runtime mapping, raster QR feasibility, and implementation gates.
- [How the Label Service Works](How_Label_Service_Works.md) — historical/current mixed architecture reference; useful evidence, but portions predate the accepted PRINT-SERVER unattended runtime and must be reconciled before being treated as current runtime authority.
- [TODO — Label Service](TODO_Label_Service.md) — engineering work list; verify items against current v3.4 and current issues before implementation.

## Runtime and Recovery

Operator/runtime recovery procedures are maintained separately under [Operational SOPs](../02_Operational_SOPs/README.md).

Do not copy runtime troubleshooting or production operator steps into this engineering portal. Link to the responsible SOP instead.
