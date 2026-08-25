# MSB Documentation Standards

## Core Documentation Principles

MSB documentation is written for the people who actually need to use it.

Many MSB volunteers are 60 years old or older, are not programmers, and may have limited experience with computers or structured technical systems. Documentation must therefore be clear, practical, and easy to navigate without requiring technical background.

The following principles apply throughout the project:

* **Documentation is task-oriented.**
  Help the reader accomplish what they came to do.

* **README files are navigation portals.**
  A README should help the reader quickly decide where to go next. It should not become a large technical manual.

* **Procedures describe how to perform a task.**
  Procedures should provide clear steps in the order they are performed.

* **Design documents explain how a system works.**
  Technical architecture, database behavior, design decisions, and implementation details belong in design documentation.

* **Operational SOPs remain separate from technical design.**
  A volunteer performing an operational task should not need to understand the underlying database or application design.

* **Link primarily to immediate children.**
  Portal pages should normally link to the documents or folders directly beneath them instead of maintaining links to documents several levels deeper.

* **Do not duplicate technical content across documents.**
  Define information in the document responsible for it and link to that document when the information is needed elsewhere.

* **Write for the least technical audience that needs the document.**
  Use plain language wherever possible. Introduce technical terminology only when the reader needs it to complete the task.

## Related Systems and Related Documents

Technical documents, procedures, and subsystem documentation should include navigable **Related Systems** and/or **Related Documents** sections when those relationships help the reader understand where the document fits or where to go next.

Use these sections only when they add value. Do not add empty sections merely to satisfy a template.

### Related Systems

Use **Related Systems** when the document has meaningful upstream, downstream, supporting, or consuming systems.

Examples include:

- a parser that feeds an ingest subsystem;
- an SQLite output database consumed by FormView and LOR2DB;
- a work-order subsystem that depends on testing and Directus;
- a wiring subsystem that consumes LOR and controller inventory data.

System names should be navigable links whenever a current repository portal or engineering entry point exists.

Prefer linking to the related system's `README.md` portal rather than to a folder listing.

### Related Documents

Use **Related Documents** when another document contains supporting detail, a responsible specification, an operating procedure, an architecture dependency, or a companion engineering reference.

Related document entries must be real Markdown links when the target exists. Do not leave plain document titles that look like navigation but cannot be clicked.

Prefer relative repository links so navigation works in GitHub, VS Code, and local repository copies.

Do not duplicate the contents of a related document. Explain the relationship briefly and link to the responsible document.

## Source of Truth and Duplication

Documentation should describe engineering intent, contracts, responsibilities, and decisions without unnecessarily copying executable implementation.

When source code, SQL, configuration, or another controlled artifact is the authoritative implementation:

- identify that artifact clearly;
- describe its engineering purpose and contract in documentation;
- link to it when useful;
- do not duplicate large implementation blocks that would have to be maintained in two places.

For example, the LOR parser source owns the executable SQLite `CREATE TABLE` and `CREATE VIEW` definitions. Engineering documentation describes why those tables and views exist, how they relate, and what downstream systems depend on them.

### Centralized implementation-object documentation

When a project has a class of shared implementation objects that can be used by multiple subsystems, maintain one predictable canonical documentation home and index for that class of objects. Subsystem documentation should link to the canonical object document instead of keeping competing copies.

For the MSB Production Database, PostgreSQL functions, procedures, and triggers are centralized under `01_Database_Foundation`. This keeps shared objects such as audit helpers, actor attribution, identity lookup/mapping, integrity helpers, and lifecycle logic discoverable as applications and workflows change.

Standalone systems may own their own implementation-specific artifacts when those artifacts are truly part of that standalone system rather than shared project infrastructure. The owning system must still be linked from related project architecture so the boundary remains visible.

## Link Quality

All current documentation should use current, navigable links.

- Repository links should normally be relative Markdown links.
- Portal links should point directly to `README.md` when doing so avoids GitHub directory-listing clutter.
- Current application URLs must remain current in engineering documentation as well as user-facing documentation.
- Historical URLs may remain only when clearly identified as historical evidence.
- When files or folders are moved, affected documentation and production navigation pages must be reviewed for stale paths.

## Usability Goal

A person arriving at a portal page should normally be able to determine where to go next within about ten seconds.

Technical depth should remain available, but it should be placed deeper in the documentation structure rather than presented to every reader.
