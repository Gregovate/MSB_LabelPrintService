# MSB Label Print Service — System Documentation

This area contains the reusable MSB documentation standards and the repository-specific engineering rules that govern `MSB_LabelPrintService`.

The documentation framework was added during the 2026-08-22 engineering-recovery effort after the current office-PC source was pushed to GitHub. It exists so future work can resume from the repository rather than reconstructing the service from conversation history or an individual workstation.

## Start Here

- [Reusable MSB Standards](Standards/README.md) — documentation, handoff, linking, document-control, SOP, source-of-truth, and cross-repository ownership rules.
- [Label Print Service Project Rules](Project_Rules/README.md) — repository-specific engineering, production-runtime, safety, rollback, and recovery rules.

## Current Engineering Context

The current Git source baseline was recovered from the MSB office PC on 2026-08-22.

The current service source identifies itself as Label Service **v3.4** and includes later reliability changes that were not reflected in the original March documentation, including:

- requester/actor improvements introduced in v3.2;
- failed-batch persistence / repeated-print-storm protection introduced in v3.3;
- rotating main service logging introduced in v3.4;
- Windows print-spooler recovery scripts present in the current repository.

The next required engineering phase is live-runtime reconnaissance of the dedicated Windows Label Print Server so Git source, deployed runtime, Brother b-PAC/driver configuration, printer queue, startup method, protected configuration, templates, logs, backup, and recovery can be documented accurately.

## Documentation Ownership Boundary

- **MSB Production Database repository** — permanent Display/Container identity, PostgreSQL label-request/batch contracts, database audit/business rules, and normal Directus operator workflow.
- **MSB_LabelPrintService** — service source, b-PAC/spooler behavior, templates/CSV generation, service-specific operation/troubleshooting, and current engineering handoff.
- **Server/runtime documentation** — dedicated Windows print-server machine, installed runtime/dependencies, machine-specific printer/driver/network/startup/backup/rebuild facts.

Do not duplicate another repository's owned implementation. Link to the responsible source and keep reciprocal handoffs current.

## Mandatory Handoff Rule

Material Label Print Service work is not complete until the responsible detailed documents and root repository README have been reviewed and updated so another engineering session can resume from Git without re-discovering accepted behavior.

## Related Repositories

- [MSB Production Database Project](https://github.com/Gregovate/MSB-Production-Database-Project)
- [MSB Server Management](https://github.com/Gregovate/MSB-Server-Management)
