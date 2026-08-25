# Linking and Navigation Standard

## Purpose

Keep repository navigation simple and reduce link maintenance as projects grow, while allowing user-facing systems to present a simpler navigation model than the underlying source repository.

## Rules

- Portal pages should link primarily to immediate children.
- When a child folder has its own README portal, link directly to that `README.md` so GitHub opens the portal content rather than placing the folder listing above it.
- Use relative Markdown links for repository content whenever practical.
- Use descriptive link text that tells the reader what the destination is for.
- Do not duplicate the same deep technical links across multiple portals.
- Cross-system links are allowed when they are genuinely needed to understand a dependency, complete a task, or reach a responsible engineering reference.
- Do not move or rename files only to make links look cleaner without first discussing the change.
- Current internal and external application links must remain current in engineering documentation as well as user-facing documentation.

## Repository Structure vs. User-Facing Navigation

Repository structure determines ownership, maintenance location, and version-control organization. A user-facing portal, intranet, scraper, or application does not need to reproduce that hierarchy literally.

When repository-controlled content is presented through a user-facing interface:

- present navigation appropriate to the intended audience and task;
- keep ordinary users inside the user-facing interface whenever practical;
- do not require users to understand repository folder structure merely to find the information they need;
- do not unintentionally send ordinary users into GitHub or another source-control interface while they follow normal navigation;
- translate repository-relative navigation into the corresponding rendered/user-facing destination when the publishing system supports it;
- provide repository/source access as an explicit contributor or engineering action rather than the default field/operator path;
- preserve a clear return path to the user's current task, Stage, subsystem, or portal context;
- exclude archive/historical material from normal user navigation unless the user deliberately chooses to view it.

A repository README may therefore be the controlled navigation source for a scraper without being the exact interface shown to field users.

## Related Systems

Use a **Related Systems** section when a document has meaningful upstream, downstream, supporting, or consuming systems.

Examples include:

- Preview Authoring → Preview Merger → LOR Data Extraction;
- LOR Data Extraction → LOR2DB Ingest;
- LOR2DB Ingest → Reconciliation → Reporting;
- parser output → FormView or the future Wiring System.

When a related system has a current repository portal or engineering entry point, its name should be a navigable Markdown link.

Do not add a Related Systems section when it does not help the reader.

## Related Documents

Use a **Related Documents** section for companion procedures, architecture documents, specifications, runbooks, or other responsible references.

- Every listed document should be a real Markdown link when the target exists.
- Prefer relative paths.
- Link to the responsible document rather than copying its content.
- Do not leave plain document titles that appear to be navigation but cannot be clicked.
- Do not add a Related Documents section when there are no useful related documents.

## Navigation Model

Use progressive navigation:

```text
Repository portal
    -> subsystem portal
        -> task or technical area
            -> detailed document
```

Cross-system engineering navigation may supplement this model when a document needs to show an actual dependency chain. It should not replace the normal portal hierarchy.

Most readers should not need to understand the complete repository structure to find the document they need.

For user-facing systems, the visible navigation may be shorter, for example:

```text
Field portal
    -> Stage
        -> current Setup instruction
```

The shorter visible path does not change repository ownership of the underlying standards, engineering contracts, templates, or source metadata.

## Repository Link Cleanup Procedure

When repository paths have changed, use two passes before redesigning published index pages.

### Pass 1 — Repair Known Moved Paths

Search current repository content for references to known former locations and replace only current navigation/documentation references that now point to moved files or folders.

Examples include moved subsystem folders, renamed documentation roots, or replaced application URLs.

Historical and archived documents may retain original paths when those paths are part of the historical record and the document is clearly identified as noncurrent.

### Pass 2 — Verify README Portal Navigation

After moved-path repairs:

1. Review every current README portal in scope.
2. Confirm every Markdown link target exists.
3. Prefer direct links to child `README.md` files where a portal exists.
4. Confirm Related Systems and Related Documents links resolve.
5. Confirm image links and current external application URLs used by the portal remain valid.
6. Record broken or ambiguous links that require human review rather than guessing a replacement.

Do not redesign separately published `index.html` pages during these two passes unless that redesign is explicitly part of the task. Treat those index pages as a separate review because they may have different navigation and audience requirements.

## Link Validation Automation

Automation should eventually reproduce the same two-pass checks programmatically.

At minimum, validation should report:

- broken relative Markdown links;
- missing README portals where a portal is expected;
- README links that point to missing files or folders;
- links to a child folder when a direct child `README.md` portal is available;
- non-clickable entries inside Related Systems or Related Documents sections;
- image links that do not resolve;
- current application URLs that still use known superseded locations;
- references to known moved paths outside clearly historical/archive material.

Automation should report problems before changing human-written navigation. Automatic rewriting should be limited to explicitly approved generated sections or simple deterministic path migrations. Published `index.html` pages remain outside automatic rewriting until their design and ownership rules are separately approved.
