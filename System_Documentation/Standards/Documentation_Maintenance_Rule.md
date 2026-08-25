# Documentation Maintenance Rule

| Document control | Value |
|---|---|
| Status | CURRENT — reusable documentation standard |
| Scope | Version-controlled engineering projects using the MSB documentation framework |
| Initial revision | 2026-08-21 |
| Owner | Project documentation owner / administrator |

## Purpose

Reverse-engineering discoveries and other durable engineering knowledge developed during project work are part of the system knowledge. They must be preserved in the repository rather than left only in conversation history.

This rule applies to engineering projects using this documentation framework and to every controlled document touched during an engineering conversation.

## Core Rule

When engineering work reveals new information that improves, corrects, or materially clarifies the understanding of a system, data source, field meaning, relationship, workflow, boundary, naming translation, implementation behavior, or operating constraint, that discovery must be captured in the appropriate repository documentation before the work is considered complete.

Conversation is a working and discovery environment. The repository is the durable project record.

## Applies to Every Document Touched

If a controlled document is edited during a conversation, review that document for discoveries made during the same work that affect information the document owns.

Do not update only the immediate sentence or section that triggered the edit while knowingly leaving newly established system knowledge absent, misleading, or inconsistent elsewhere in that same document.

This does not mean rewriting the document. Preserve valid existing content, history, terminology, structure, and ownership. Make focused additive corrections or clarifications where practical.

## Reverse-Engineering Discoveries

Reverse-engineered knowledge must be documented at the level actually established by evidence.

Examples include:

- source-schema field meanings and project terminology translations;
- type-dependent interpretation of serialized fields;
- undocumented relationships between source objects;
- identity and grouping behavior discovered from source files or running systems;
- path-resolution behavior;
- database or application dependencies;
- compatibility assumptions;
- operational constraints revealed during testing;
- limitations where the meaning of a source field is still unknown.

Do not promote an inference into a documented fact unless the evidence supports it. When a meaning remains uncertain, preserve the observed behavior and the uncertainty.

## Documentation Placement

Record discoveries in the document that owns the subject whenever possible.

Use the document-control ownership hierarchy defined by the repository:

- reusable cross-project standards belong in the repository's standards area;
- project-specific governance belongs in the repository's project-rules or equivalent governance area;
- subsystem engineering discoveries belong in the responsible subsystem architecture/reference documentation;
- operator workflow discoveries that change how work is performed belong in the responsible procedure or SOP.

Do not create a new document merely to avoid maintaining the current responsible document. Create a new controlled reference only when the information has a distinct durable purpose, then link it through the responsible navigation.

## Naming and Terminology

When reverse engineering establishes a translation between source-system terminology and project terminology, preserve that translation explicitly in the repository.

Prefer exact source-system names when discussing the source schema and established human-readable project names when discussing project meaning. Avoid introducing conversation-specific aliases when an established source name or controlled project term already exists.

## Closeout Requirement

Before closing material engineering work:

1. Review the controlled documents edited during the conversation.
2. Identify durable discoveries made during the work that affect what those documents own.
3. Add focused corrections or clarifications without unnecessarily rewriting valid documentation.
4. Update the responsible subsystem documentation for discoveries that belong outside the files already being edited.
5. Review navigation when a new controlled reference was created or moved.
6. Commit the documentation with the engineering work or as a clearly related documentation commit.

Work is not fully documented if a future maintainer or future engineering session would have to reconstruct an established discovery from conversation history instead of finding it in the repository.

## Relationship to Existing Standards

This rule strengthens the existing requirements in:

- [`Document_Control_Standard.md`](Document_Control_Standard.md), which requires accepted material decisions to be promoted from conversation into controlled repository documentation; and
- [`Prompt_Guidelines.md`](Prompt_Guidelines.md), which treats the repository and authoritative artifacts as the durable source of truth.

This rule does not replace those standards. It establishes the explicit maintenance obligation for discoveries made during engineering conversations.
