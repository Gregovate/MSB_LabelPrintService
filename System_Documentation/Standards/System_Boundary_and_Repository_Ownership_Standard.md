# System Boundary and Repository Ownership Standard

## Purpose

This standard defines how MSB separates the Production Database, integrated dependencies, dedicated applications, and supporting subsystems across repositories without losing a clear source of truth.

The goal is not to keep every related application inside the Production Database repository. The goal is to make ownership and dependency direction explicit so each repository can evolve independently without duplicating or competing with authoritative data and business rules.

## Core Rule

A repository boundary does **not** determine data authority.

For every subsystem, document separately:

1. **Data authority** — which system owns the authoritative data or configuration.
2. **Business-rule authority** — where lifecycle rules, constraints, and shared workflow contracts are enforced.
3. **Application responsibility** — what the user-facing or supporting application does.
4. **Dependency direction** — which system can continue to operate if another subsystem is unavailable.
5. **Repository ownership** — where implementation, deployment, and subsystem-specific documentation belong.

Do not duplicate authoritative data or redefine shared business rules merely because an application lives in a separate repository.

## System Relationship Classes

### 1. Core Database Subsystem

A Core Database Subsystem is part of the Production Database's permanent identity, relationships, history, or operational business model.

Examples include Containers, Testing, Work Orders, People/Identity, and permanent controller inventory.

For these systems:

- PostgreSQL is the system of record unless an explicit upstream authority is documented.
- shared identities, relationships, lifecycle state, constraints, and database-side business rules remain owned by the Production Database;
- a user interface may be Directus today and a dedicated application later without moving data authority out of PostgreSQL;
- the Production Database engineering README documents the subsystem contract even if the application implementation lives elsewhere.

### 2. Integrated Upstream Dependency

An Integrated Upstream Dependency supplies authoritative source data that the Production Database relies on.

The Production Database cannot independently redefine that upstream information.

**MSB example: LOR / LOR2DB**

- Light-O-Rama remains authoritative for show topology and wiring configuration.
- LOR2DB is the controlled ingest/reconciliation boundary that brings LOR-derived data into PostgreSQL.
- PostgreSQL stores, relates, reconciles, enriches, and operationally uses the imported data.
- If the ingest path is stale or incorrect, affected Production Database data can become stale or incorrect.

Because this is an integrated dependency, its contracts must be documented closely with the Production Database architecture even when implementation is maintained as a distinct project.

### 3. Dedicated Database-Backed Operational Application

A Dedicated Database-Backed Operational Application provides a task-focused user experience over a Production Database subsystem.

It may read and write Production Database records, but PostgreSQL remains authoritative for shared data and business state.

**MSB example: future Work Order application**

Directus currently provides work-order editing, triage, assignment, and workflow automation, but its general-purpose interface is not adequate for every recurring operator task.

A dedicated Work Order application may therefore live in its own repository and provide the task-focused interface while:

- using Production Database work-order identities and relationships;
- reading and writing PostgreSQL through an approved application/API boundary;
- respecting PostgreSQL constraints and lifecycle rules;
- preserving People/Identity, Testing, Display, Stage, and Work Area relationships;
- avoiding a second work-order database or competing lifecycle model.

The Production Database repository owns the Work Order data model and integration contract. The application repository owns the application's code, UI, deployment, and application-specific implementation documentation.

### 4. Dedicated Database-Backed Presentation / Field Application

A Dedicated Database-Backed Presentation or Field Application consumes Production Database data to present specialized information or support field work.

It may also write approved operational metadata, but it must not redefine an upstream authoritative source.

**MSB example: future Wiring application**

FormView currently presents wiring information from parser-produced SQLite data. The future Wiring application should use PostgreSQL as its operational data source rather than maintaining an independent SQLite operational database.

The authority chain remains:

```text
Light-O-Rama
    -> LOR2DB
        -> PostgreSQL Production Database
            -> Wiring application
```

Therefore:

- LOR remains authoritative for controller assignments, channel numbers/ranges, DMX/network assignments, and show wiring topology;
- LOR2DB brings that authoritative topology into PostgreSQL;
- PostgreSQL becomes the shared operational source consumed by the Wiring application and can add permanent identities, inventory relationships, field notes, and other database-owned information;
- the Wiring application provides task-focused lookup, presentation, and field workflow;
- the Wiring application must not create a competing topology-authoring system.

Its implementation may live in a separate repository. The Production Database Wiring engineering README owns the integration and authority contract.

### 5. External Supporting Subsystem

An External Supporting Subsystem consumes Production Database information or events but is not required for the Production Database to remain authoritative and internally consistent.

**MSB example: MSB_LabelPrintService**

- the Production Database owns the asset/container/display identities and label-request state;
- the Label Print Service consumes that information and produces physical labels;
- the print service has its own dedicated print server, runtime, deployment, troubleshooting, and repository;
- if the print service is unavailable, label printing stops, but the Production Database remains authoritative and usable.

The Production Database documentation should describe the integration point and normal operator action. The supporting subsystem repository should own its service architecture, deployment, operation, and troubleshooting documentation.

## Repository Ownership Rule

A subsystem is a good candidate for a separate repository when it has an independently meaningful application or service lifecycle, such as:

- its own deployed application or service;
- its own server/runtime environment;
- independent release/deployment needs;
- substantial UI or application code unrelated to the database implementation itself;
- specialized operational troubleshooting;
- the ability to be developed or restarted without changing the Production Database schema.

A separate repository must **not** become a separate source of truth merely for convenience.

## What Stays in the Production Database Repository

Even when a dedicated application lives elsewhere, the Production Database repository retains documentation for:

- authoritative PostgreSQL identities and relationships;
- database-owned lifecycle and business rules;
- constraints, procedures, triggers, and shared database contracts;
- upstream authority boundaries;
- downstream consumer/integration contracts;
- cross-subsystem dependencies;
- the responsible engineering README/handoff.

Do not copy the application's implementation manual into the Production Database repository.

## What Belongs in the Dedicated Application Repository

The application or service repository owns:

- application source code;
- UI implementation;
- application-specific API/client code;
- configuration and deployment;
- runtime/service management;
- application-specific tests;
- application engineering details;
- service-specific operator troubleshooting when applicable.

It should link back to the responsible Production Database engineering contract when it depends on Production Database data or business rules.

## Directus Boundary

Directus is a shared implementation platform, not the source of truth for Production Database business data.

Use Directus where its interface and Flows are effective. When Directus is inadequate for a repeated operational task, a dedicated application may replace that user experience without moving authoritative Production Database data into a new store.

The replacement application should consume the same PostgreSQL system of record and preserve the same subsystem contracts.

## Documentation Requirement for Cross-Repository Systems

Every Production Database subsystem that has a separate application or supporting repository should identify, when applicable:

- **Relationship Class** — one of the classes in this standard;
- **Authoritative Data / Configuration**;
- **Production Database Responsibility**;
- **External Repository Responsibility**;
- **Read/Write Direction**;
- **Failure Boundary** — what continues working if the external subsystem is unavailable;
- **Related Repository** — direct link to its README or engineering entry point.

The external repository should contain a reciprocal link to the Production Database subsystem README when practical.

## Current MSB Examples

| System | Relationship Class | Authority / System of Record | Repository Boundary |
|---|---|---|---|
| LOR2DB | Integrated Upstream Dependency | LOR for show topology; PostgreSQL for database-owned identity/relationships after controlled ingest | Closely integrated with Production Database architecture |
| Work Orders | Core Database Subsystem + Dedicated Database-Backed Operational Application | PostgreSQL | Database model here; dedicated task UI may be separate repo |
| Wiring | Core database integration + Dedicated Database-Backed Presentation / Field Application | LOR for topology; PostgreSQL for shared operational data | Database integration here; dedicated Wiring app may be separate repo |
| MSB_LabelPrintService | External Supporting Subsystem | PostgreSQL for label source data | Separate service repo and dedicated print server |

## Design Test

Before creating or expanding a repository, answer these questions:

1. If this application disappears tomorrow, what authoritative data is lost?
2. Can the Production Database still remain internally correct without it?
3. Does the application need to author authoritative data, or only operate on data owned elsewhere?
4. Which business rules must remain enforceable even if the UI changes?
5. Where should another developer look to understand the integration contract?

If these answers are not clear, the system boundary is not documented well enough yet.
