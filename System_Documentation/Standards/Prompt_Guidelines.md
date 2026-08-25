# Prompt Guidelines

## Purpose

This document defines how Greg and ChatGPT work together on version-controlled engineering projects and their documentation.

These guidelines support the standards in this folder. They do not replace the technical content of the systems being developed.

The working contract is intentionally reusable. Project-specific repositories may add local requirements, but they should build on these rules rather than requiring the same working practices to be reconstructed from conversation history.

## Working Rules

- Treat the current repository and its authoritative implementation artifacts as the durable source of truth; do not rely on conversation memory when the repository can answer the question.
- Review the actual repository structure, responsible README, and current files before proposing changes.
- Follow the project's documented standards before inventing new structure, terminology, or conventions.
- Work one step at a time when the requested task is staged.
- Gather evidence before redesigning or modifying production systems.
- Do not change direction in the middle of an agreed task unless a real problem is found and discussed.
- Do not move, rename, or reorganize files unless Greg approves it first.
- Do not invent folders, schemas, naming conventions, or architectural boundaries when the existing project or source artifacts can establish them.
- Do not rewrite working technical documentation merely to make it fit a portal format.
- Preserve technical meaning, established terminology, safety boundaries, operational controls, and settled engineering decisions.
- Clearly distinguish current implementation, approved design, legacy behavior, planned work, and unresolved ideas.
- Keep operational SOPs separate from technical design documentation.
- Keep portal pages short and navigation-focused while preserving the engineering handoff information required by `README_Portal_Standard.md`.
- Link primarily to immediate children rather than duplicating deep links throughout the repository.
- Do not duplicate technical content when a responsible document already exists; link to it instead.
- Write for the least technical audience that needs the specific document.
- Do not make volunteer-facing documentation more technical than the task requires.
- When a document contains version or revision control, preserve it and follow the applicable standards before editing.
- Revision history must remain reverse chronological when used.
- Use repository evidence instead of assumptions whenever the current state can be inspected.
- Include navigable `Related Systems` and `Related Documents` sections when they help the reader understand dependencies or find the next responsible document.
- Do not leave plain-text document or system names in navigation sections when a valid Markdown link can be provided.
- When implementation code, SQL, configuration, drawings, source datasets, or other artifacts are authoritative, document the engineering contract without unnecessarily duplicating the implementation.
- Preserve superseded engineering evidence when it remains useful, but archive it rather than leaving competing active authorities.
- When repository paths change, review affected internal links, source-code documentation references, and externally published navigation.
- Material subsystem work is not complete until the responsible README has been reviewed and updated when necessary to preserve the current engineering handoff.

## Before Beginning Work

For repository engineering or documentation work, first determine:

1. Which repository, branch, and subsystem are in scope.
2. Whether the working state is safe for the requested changes when local or remote version-control state matters.
3. Which README is the responsible subsystem handoff and what it says about current state and open work.
4. Which engineering documents, procedures, code, SQL, configuration, drawings, datasets, applications, or external source systems are authoritative.
5. What is current implementation versus planned or historical behavior.
6. Which related systems own adjacent information so responsibilities are not duplicated.
7. What document type is being changed: portal, procedure, SOP, design, runbook, report, or other technical reference.
8. Who needs to read it.
9. Whether the requested change affects links, document control, revision history, screenshots, related systems, or related documents.

Do not add complexity that does not help the intended reader or engineering task.

## Repository and Version-Control Changes

When making repository changes through GitHub or another version-control workflow:

- inspect the current file before replacing it;
- inspect the current repository tree when paths or navigation are involved;
- respect the agreed branch and do not silently change branches or repository scope;
- make only the changes required for the current step;
- use clear commit messages;
- report exactly what was changed;
- identify any issue discovered but intentionally left unchanged;
- do not claim links, paths, implementation state, or deployment state are current without checking when they can be inspected;
- do not overwrite uncommitted local work or create avoidable divergence between local and remote work;
- preserve history through version control and archive superseded documentation when it remains useful evidence.

The repository, not conversation history, is the durable source for these conventions and for the subsystem handoff.

## Generic Project Engineering Prompt

Use this prompt when starting or resuming work with ChatGPT on a version-controlled engineering project that follows these standards. Replace project-specific placeholders as needed. A repository may provide additional local standards or a subsystem-specific resume prompt.

```text
Work on this project using the current version-controlled repository and its authoritative source artifacts as the durable source of truth.

Before making changes:
1. Confirm the repository, branch, and subsystem in scope.
2. Review the actual current repository tree and the responsible subsystem README.
3. Read and follow the project's documentation, version-control, linking, naming, and engineering standards before proposing new structure or conventions.
4. Read the engineering documents, procedures, source code, SQL, configuration, drawings, datasets, applications, or external-system references identified by the subsystem README as authoritative.
5. Determine what is currently implemented, what is approved design, what is legacy/historical, what is planned, and what remains unresolved.
6. Identify related systems and ownership boundaries before duplicating data, documentation, or responsibility.
7. Gather evidence first. Do not redesign a production system or invent folders, schemas, naming conventions, or architecture simply because information appears incomplete.

Working rules:
- Preserve established technical meaning, identities, terminology, safety controls, operational controls, and settled engineering decisions.
- Keep engineering/design documentation separate from operator procedures and SOPs.
- Write documentation for the least technical audience that actually needs that document.
- README files are navigation portals and, for active engineering subsystems, the current development handoff.
- Do not duplicate information already owned by another responsible document or authoritative implementation; link or reference it instead.
- Clearly distinguish current state from future design ideas.
- Preserve useful engineering history, but archive superseded material rather than leaving multiple active authorities.
- Do not move or rename files, change architectural boundaries, or make production changes unless the current task authorizes them.
- Work in focused steps and stop to discuss a real conflict or unexpected condition before changing direction.

Version-control rules:
- Inspect current repository state before writes when local/remote divergence or uncommitted work could matter.
- Respect the agreed repository and branch.
- Make focused commits with clear messages.
- Do not overwrite uncommitted work or silently resolve conflicts by discarding information.
- Report exactly what changed and what was intentionally left unchanged.

Documentation and navigation rules:
- Follow the repository's README, document-control, Markdown, linking, and navigation standards.
- Prefer repository-relative links for repository content.
- Use real navigable links for related systems and related documents when targets exist.
- Validate links, paths, screenshots, and current application URLs affected by the work.
- When a path changes, review dependent documentation, source references, and externally published navigation identified by the project.

Mandatory closeout:
1. Update the responsible engineering/design documents, procedures, SOPs, or references whose owned information changed.
2. Review the subsystem README after the implementation and detailed documentation are current.
3. Update that README so it accurately records the resulting current state, design intent where needed, authoritative sources, system boundaries/dependencies, known limitations/open work, and the next development starting point.
4. Verify its navigation and related-system/document links.
5. Commit the README handoff with the completed work.

Do not consider material subsystem work complete if the next session would have to reconstruct settled decisions from chat history, old commits, or obsolete documents instead of resuming from the repository.
```

## Subsystem Resume Prompt

Each active or incomplete engineering subsystem should include, directly or by link from its README, a concise subsystem-specific resume prompt when that prompt materially improves continuity.

The subsystem prompt should not repeat the generic working contract. It should identify only the context unique to that subsystem, such as:

- the subsystem's purpose and ownership boundary;
- current implementation/deployment status;
- authoritative engineering documents and implementation files;
- authoritative external artifacts or source systems;
- permanent identity or data-contract rules that must not be broken;
- known limitations and unresolved decisions;
- related subsystems that must be reviewed before changing interfaces;
- the specific next development or validation starting point.

A useful subsystem prompt should allow a new work session to read the README, follow its authoritative references, and resume without asking Greg to re-explain settled architecture.

## Reusable MSB Documentation Prompt

For documentation-only work in the MSB Production Database Project, use the generic project engineering prompt above together with the current standards under `System_Documentation/Standards/`, especially:

- `Documentation_Standards.md`;
- `README_Portal_Standard.md` when working on a README or portal;
- `Linking_and_Navigation_Standard.md` when links or navigation are involved;
- `Document_Control_Standard.md` when revision control applies;
- this `Prompt_Guidelines.md`.

The current task still controls scope. If the task is to review one README, review one README. If the task is a repository-wide audit, inspect the entire agreed scope before making broad changes.

The purpose of the reusable prompts is consistency: the same source-of-truth, version-control, engineering, documentation, navigation, history-preservation, and closeout rules should apply without Greg having to restate them for every project or every work session.
