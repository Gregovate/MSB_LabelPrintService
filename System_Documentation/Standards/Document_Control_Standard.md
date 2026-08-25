# Document Control Standard

## Purpose

This standard defines how controlled documentation is created, maintained, reviewed, superseded, archived, and published across version-controlled MSB projects.

It is intentionally reusable across repositories. Project-specific rules may add requirements, but should not redefine the common document-control model.

The goal is simple: a reader, contributor, or future work session should be able to determine which document is current, who owns it, where its authoritative source lives, and what happened to the document it replaced.

## Core Principle

Conversation, email, chat history, and working notes are not durable documentation authority.

When a material decision is accepted, it must be recorded in the appropriate controlled repository document before the work is considered complete.

Use this ownership hierarchy:

1. **Reusable rule affecting multiple repositories** — update the applicable document under `System_Documentation/Standards/` and synchronize the approved standard to the repositories that use the common standards set.
2. **Repository-specific governance or working rule** — record it under that repository's `System_Documentation/Project_Rules/` or other clearly designated project-governance location.
3. **Subsystem-specific engineering decision** — record it in the responsible subsystem engineering documentation and update the subsystem README handoff when necessary.
4. **Operator task change** — update the responsible current procedure or SOP.

Do not leave an accepted cross-thread or cross-system decision only in a conversation.

## One Current Authority

A controlled subject should have one clearly identifiable current authority for its owned information.

Do not maintain competing active documents that independently define the same rule, procedure, engineering contract, or operational requirement.

Supporting documents may summarize or reference the responsible authority, but should link to it rather than maintain a second copy of the same controlled content.

When implementation code, SQL, configuration, source datasets, drawings, external systems, or other artifacts are the actual implementation authority, documentation should identify that authority and describe its contract without pretending the Markdown document itself is the executable source of truth.

## Document States

Use document states deliberately. The exact metadata format may vary by document type, but the meaning must remain consistent.

### CURRENT

The approved document for present use.

There should normally be only one current document for a specific procedure, policy, engineering contract, or other controlled purpose.

### DRAFT

Work in progress, under review, or being tested.

A draft must not be presented through normal operator navigation as though it were the approved procedure unless the interface clearly identifies it as draft material.

### RETIRED

No longer approved for current use, but intentionally retained outside the normal archive because there is a specific reason to keep it directly accessible.

Use this sparingly. Most superseded documents should be archived instead.

### ARCHIVED

Historical or superseded material retained as evidence, reference, or recovery history.

Archived content is not current authority and should not compete with current documentation in normal user-facing navigation.

## Source Document and Published Copies

Every controlled document must have a clearly understood authoritative source.

When the same content appears in more than one format or system, identify which copy is edited and controlled and which copies are derived, published, exported, or convenience versions.

Examples may include:

- Markdown source with a generated or manually published PDF;
- repository source rendered into an intranet or documentation portal;
- an external collaborative document linked from a repository-controlled index;
- a working source file used to produce a field-reference image or drawing.

A published copy must not silently become a competing authority merely because it is easier to access.

Pointer, shortcut, or link files do not by themselves constitute a portable document source. When an externally hosted document is authoritative, its durable identifier and ownership must be documented in a controlled repository location so the relationship can be reconstructed.

## Repository Structure and User-Facing Presentation

Repository structure determines document ownership, maintenance location, and version-control organization.

User-facing navigation does not need to expose that repository structure literally.

When repository documentation is rendered through an intranet, documentation portal, scraper, or other user-facing interface:

- present navigation appropriate to the intended audience;
- keep users within the rendered interface whenever practical;
- do not require ordinary users to understand the repository hierarchy;
- do not unintentionally send users into GitHub or another source-control interface when they are following normal operational navigation;
- provide access to repository source as an explicit contributor or engineering action when appropriate.

The repository remains the controlled organization layer even when the published interface presents a simpler navigation model.

## Document Ownership

Each controlled document must have an identifiable owner, either a named person or a responsible role.

The owner is responsible for determining whether the document remains current and for coordinating review when the underlying system, workflow, or requirement changes.

Ownership does not mean only the owner may edit the document. It identifies who is responsible for its continued correctness.

## Review and Approval

Review requirements should match the consequence of the document.

At minimum:

- technical documents should be reviewed when their owned system behavior or contract materially changes;
- operator procedures should be reviewed when the task, interface, safety requirement, folder structure, or required sequence changes;
- reusable standards should be reviewed before synchronization to other repositories;
- templates should be reviewed whenever the governing standard changes in a way that affects their structure or required fields.

When a project requires explicit approval, record the approving person or role in the document's control metadata or change history.

Do not invent approval records for historical documents when approval cannot be established.

## Revision and Change History

Use revision history when it helps a maintainer understand material changes, approvals, or the reason a document was replaced.

When a change log is used:

- keep entries concise and meaningful;
- record material changes rather than every spelling or formatting correction;
- include the change date;
- identify the person or role responsible when the document type requires it;
- include approval information when approval is part of the workflow;
- keep the history in the order defined by the applicable document template or project rule, and use that order consistently within the document family.

Git history remains the detailed version-control record. A document change log should summarize important human-facing revisions rather than duplicate the full commit history.

## Superseding and Archiving Documents

When a current document is replaced:

1. Confirm the replacement is ready to become the current authority.
2. Update normal navigation to point to the replacement.
3. Move the superseded document to the approved archive location when preservation is useful or required.
4. Preserve enough identity to understand what the archived document was and what replaced it.
5. Remove the superseded copy from normal current/operator navigation.
6. Review links that may still point to the superseded location.

Do not delete useful historical engineering evidence merely to make a folder look clean.

Do not leave obsolete documents mixed with current procedures when an archive location exists.

## Archive Locations

Archive material as close as practical to the area that owns it unless a project has a designated central archive.

A project may use structures such as:

```text
<document area>/Archive/
```

or a repository-level historical archive when that better preserves engineering history.

The important requirement is that current and historical authority remain distinguishable.

## Templates

Templates are controlled documentation assets.

A template defines the expected structure for a document type; it does not replace the standard governing that type.

Different document types may and often should use different templates. For example, an operator instruction, field setup procedure, engineering design document, and administrative procedure do not need identical layouts.

Templates must:

- follow the applicable reusable standards;
- identify their intended document type and audience;
- avoid project-specific requirements unless the template itself is intentionally project-specific;
- be stored in a predictable controlled location;
- be updated when the governing standard materially changes;
- avoid relying on fragile manual formatting when a durable structural representation is available.

Project-specific templates may live in that project's `System_Documentation/Templates/` or another documented template location.

## Images and Supporting Assets

Images and supporting files are part of document control when a current document depends on them.

The applicable project or document-type standard should define where those assets belong.

General rules:

- use predictable locations;
- keep an image close to the documentation area that owns it when practical;
- use shared/public assets for genuinely reusable items such as organization branding rather than unnecessary copies;
- do not create multiple ambiguous image locations for the same document family;
- use relative repository paths for repository-controlled assets whenever practical;
- archive or remove obsolete supporting assets when they would otherwise create confusion or appear in generated documentation.

## Navigation and Discoverability

A current controlled document is not complete merely because the file exists.

When normal discovery depends on README portals, indexes, generated navigation, or another publishing system, review the applicable navigation entry after creating, replacing, moving, or retiring the document.

README files should remain navigation portals rather than becoming duplicate copies of the documents they organize.

Archive material should normally be excluded from ordinary operator navigation unless the user deliberately chooses to view historical information.

Follow `Linking_and_Navigation_Standard.md` for repository navigation rules.

## Cross-Repository Reusable Standards

Repositories that adopt the common MSB documentation framework should remain self-contained: a repository should not need to read another project's repository merely to discover the documentation rules it is expected to follow.

Approved reusable standards should therefore be synchronized into each participating repository's `System_Documentation/Standards/` area.

Project-specific requirements remain local to the repository and must not be inserted into the reusable standard merely because several projects happen to interact.

Until a controlled automated synchronization process is approved, synchronization should be deliberate and reviewed. Do not automatically overwrite locally modified standards without first identifying the difference.

## Required Closeout

Before considering material documentation work complete:

1. Confirm the correct current authority was updated.
2. Confirm accepted cross-thread decisions were promoted to the appropriate reusable standard, project rule, subsystem document, or operator procedure.
3. Review whether the document's owner, state, source relationship, revision information, and related links remain accurate.
4. Archive superseded material when required.
5. Review the responsible README or other navigation entry.
6. Verify affected links and supporting assets.
7. Commit the controlled source through the project's version-control workflow.
8. When a reusable standard changed, identify the other participating repositories that need the approved version synchronized.

Documentation work is not complete if the next contributor or work session would need to reconstruct a settled decision from conversation history instead of finding it in the controlled repository.

## Related Standards

- [Documentation Standards](Documentation_Standards.md)
- [README Portal Standard](README_Portal_Standard.md)
- [Operational SOP Standard](Operational_SOP_Standard.md)
- [Linking and Navigation Standard](Linking_and_Navigation_Standard.md)
- [Markdown Style Guide](Markdown_Style_Guide.md)
- [Prompt Guidelines](Prompt_Guidelines.md)
