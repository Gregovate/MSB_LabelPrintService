# Label Print Service Engineering Rules

| Document control | Value |
|---|---|
| Status | CURRENT — repository-specific engineering rule |
| Initial revision | 2026-08-22 |
| Owner | MSB Database Administrator / Label Print Service maintainer |
| Repository | `Gregovate/MSB_LabelPrintService` |

## Purpose

These rules govern engineering, recovery, documentation, testing, deployment, and troubleshooting of the MSB Label Print Service and its dedicated Windows print-server runtime.

They supplement the reusable MSB standards under `../Standards/` and must not redefine Production Database authority.

## Core System Boundary

`MSB_LabelPrintService` is an **External Supporting Subsystem** of the MSB Production Database.

The authority chain is:

```text
MSB Production Database / Directus
    -> PostgreSQL label-request and batch contracts
        -> MSB Label Print Service
            -> Brother b-PAC / Windows print spooler
                -> Brother P-touch PT-P950NW
                    -> physical labels
```

The Production Database remains authoritative for permanent asset identity, label-request state, batch/history relationships, and database-owned audit/business rules.

The Label Print Service owns application-specific polling, snapshot consumption, CSV generation, Brother template population, b-PAC submission, Windows spooler verification, service logging, and service-specific recovery behavior.

The dedicated Windows print server is a production runtime and must be documented as such. Machine/runtime administration belongs with the server/runtime documentation boundary rather than being inferred from service source code.

## Evidence Before Modification

Before changing service behavior:

1. Inspect the current Git branch and current repository source.
2. Read the current root README/handoff and applicable documents under `docs/`.
3. Verify the actual deployed copy on the dedicated print server when deployment state matters.
4. Verify the active service version, startup path, Python environment, Brother b-PAC installation, printer queue, templates, and protected configuration rather than assuming March documentation remains current.
5. Compare repository source with the deployed runtime before replacing or refactoring working code.
6. Record material discoveries in the responsible repository documentation before closing the work.

The live production system outranks stale documentation when the two conflict. The discrepancy must then be documented and reconciled.

## Preserve the Accepted Production Baseline

Do not replace, refactor, or broadly clean up the working service merely because older code is untidy.

The current recovered source baseline includes `label_poll_service_v3.py`, which identifies itself as Label Service **v3.4** and contains later reliability work through 2026-04-16.

The accepted baseline includes, among other behavior:

- polling the Production Database for label requests;
- snapshot batch creation;
- one-label-per-Display behavior;
- two-labels-per-Container behavior;
- Brother b-PAC template printing;
- Windows spooler verification rather than trusting b-PAC completion callbacks;
- queue-empty and active-batch safety guards;
- requester/actor attribution introduced in v3.2;
- persistence of failed batch rows before physical printing so failed jobs do not silently requeue in a print storm;
- rotating main service logging introduced in v3.4.

Any change affecting those behaviors requires explicit review and regression validation.

## Print-Storm Safety Rule

The April 2026 repeated-print failure is a critical historical safety boundary.

Do not remove or weaken behavior that ensures a failed physical print leaves a durable failed batch state and does not cause the same active `print_label` request to be re-created indefinitely.

Any change to transaction boundaries, batch commits, failed-batch guards, original-row flag clearing, automatic retries, or spooler verification must be treated as high-risk printing logic.

## Production Database Boundary

Do not move Production Database authority into this repository.

This repository must not independently redefine:

- permanent Display identity;
- permanent Container identity;
- Storage Location identity;
- canonical scan payload rules;
- label request lifecycle stored in PostgreSQL;
- database audit/person attribution contracts;
- shared Production Database business rules.

If the service requires a database-contract change, document and implement the database side in `Gregovate/MSB-Production-Database-Project` through its normal engineering workflow, then update this repository's integration documentation.

## Source and Runtime Boundary

The Git repository is the durable source for service code, templates intended for source control, SQL/query files, example configuration, service-specific documentation, and recovery scripts appropriate for version control.

The dedicated Windows print server owns the live runtime state, including:

- deployed working directory;
- installed Python/runtime dependencies;
- Brother b-PAC SDK installation;
- Brother Windows printer driver and queue;
- Start Label Service shortcut/startup method;
- live protected configuration such as `config.local.ini`;
- machine-specific network/printer configuration;
- runtime logs and state;
- Windows spooler state.

Do not assume a file is deployed merely because it exists in Git. Do not assume Git is stale merely because an older document says otherwise. Compare when it matters.

## Secrets and Protected Configuration

Never commit:

- live database passwords;
- Windows account passwords;
- private keys or tokens;
- production `config.local.ini` when it contains credentials;
- other protected authentication material.

Example configuration may document keys, paths, service account names, hostnames, or placeholder values without exposing live secrets.

If a real credential is discovered in Git, stop and treat it as a credential-exposure issue requiring rotation and repository cleanup planning.

## Version-Control Rule

Do not perform engineering work directly on `main` unless the user explicitly authorizes an emergency production correction.

Normal work uses a dedicated branch, focused commits, review, and controlled merge.

Before writes:

- inspect the current branch;
- inspect local/remote divergence when local work may exist;
- do not overwrite uncommitted local work;
- do not silently discard runtime-only changes;
- preserve useful engineering history.

## Deployment / Rollback Rule

Before modifying the production print server:

1. Identify the exact deployed files/configuration being changed.
2. Record the current service version and source commit when known.
3. Preserve a rollback copy or other reproducible restore point.
4. Verify the current printer/queue state.
5. Make only the approved change.
6. Start/restart using the documented operating method.
7. Run the required service and physical-print verification.
8. Confirm failure behavior as well as successful printing when the change affects queue/batch logic.
9. Update the current engineering handoff and runtime documentation.

Do not use an old source file merely because its filename contains an older version number. Verify what actually represents the immediately preceding accepted production behavior.

## Spooler Recovery Rule

Spooler-clearing scripts are destructive to queued print jobs.

Use `killspooler.bat`, `killspooler.ps1`, or equivalent spool-directory clearing only as a controlled recovery action after confirming that queued jobs may safely be discarded.

Do not make spooler clearing an automatic normal startup behavior.

The recovery procedure must document:

- when spooler clearing is appropriate;
- what pending print jobs will be lost;
- how PostgreSQL batch/request state is checked afterward;
- how duplicate physical printing is prevented during recovery.

## Operator Documentation Boundary

The Production Database repository owns the normal operator task for requesting labels from Directus.

This repository owns operator/admin procedures specific to the print service and dedicated print server, such as:

- checking whether the label service is running;
- starting/stopping the service;
- checking the printer queue;
- identifying safe retry conditions;
- recovering from a stuck queue;
- checking logs;
- verifying physical printer readiness.

Do not require ordinary label-printing users to understand Python, b-PAC, SQL, Git, or Windows service internals.

## Documentation Handoff Rule

Material work is not complete until the repository documentation can carry the next engineering session without chat history.

At closeout:

1. Update the detailed engineering/runtime/procedure documents whose owned information changed.
2. Review the root README as the current repository handoff.
3. Record current service/deployment state, authoritative sources, dependencies, known limitations, and exact resume point.
4. Keep cross-repository links current with `MSB-Production-Database-Project` and the responsible server/runtime documentation.
5. Preserve historical March documents when useful, but clearly distinguish historical statements from current v3.4 behavior.

## Current Recovery Priority

The present engineering-recovery effort should proceed in this order:

```text
1. Establish repository governance and standards
2. Reconstruct current Git source / documentation state
3. Inspect the live dedicated Windows print server
4. Compare deployed runtime with Git source
5. Document current architecture, deployment, startup, configuration boundary, b-PAC/driver/queue, templates, logs, backup, and recovery
6. Reconcile stale March-era documentation with current v3.4 behavior
7. Update reciprocal Production Database / Server Management handoffs
8. Only then consider new Label Print Service features or structural refactoring
```

Do not redesign the working label-printing system during this recovery phase unless a verified defect requires an approved change.

## Related Standards

- [Documentation Standards](../Standards/Documentation_Standards.md)
- [Documentation Maintenance Rule](../Standards/Documentation_Maintenance_Rule.md)
- [Document Control Standard](../Standards/Document_Control_Standard.md)
- [README Portal Standard](../Standards/README_Portal_Standard.md)
- [Prompt Guidelines](../Standards/Prompt_Guidelines.md)
- [System Boundary and Repository Ownership Standard](../Standards/System_Boundary_and_Repository_Ownership_Standard.md)
