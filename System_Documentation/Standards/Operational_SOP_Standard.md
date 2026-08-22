# Operational SOP Standard

## Purpose

This standard defines how MSB operator procedures are created, named, placed, written, illustrated, and linked so they are easy for volunteers to use and can be indexed automatically in the future.

Operational SOPs explain **how to perform a task**. They do not replace engineering architecture or implementation documentation.

## Operator Navigation Boundary

The normal browsing path for operators must remain operational by default.

An operator moving through README portals should normally follow:

```text
Operational SOP portal -> task-area portal -> plain-language task procedure
```

Do not place engineering documents, SQL procedures, trigger documentation, architecture handoffs, implementation notes, or other technical references in the normal operator procedure-selection table.

Engineering material may still be linked when it is useful to someone who wants to understand how the system works. Put those links in a clearly labeled section such as **Related Engineering** or **Related Documents**, separate from the normal task-navigation table.

The operator should have to deliberately choose to leave the operational documentation path and enter engineering documentation.

## Task Granularity and Workflow Portals

Prefer one plain-language procedure for each real operator task or decision point rather than one large end-to-end manual when the workflow can be safely divided.

A task-area `README.md` should act as the workflow map. It should help the operator answer **What am I trying to do right now?** and lead directly to the appropriate short procedure.

Each procedure should contain enough information to complete its task without requiring the operator to read the entire workflow documentation first.

Do not split a task so finely that an operator must constantly switch documents to complete one normal action. The goal is understandable task-sized instructions, not the largest or smallest possible number of files.

## Workflow Navigation Inside Procedures

When a task area contains a sequence of related procedures, each procedure must make it easy to move through that workflow without returning to the GitHub folder view.

Place a compact navigation line near the **top** of the procedure and repeat it at the **bottom**.

Use this pattern when applicable:

```markdown
[← Previous: Previous Task](Previous_Task.md) | [↑ Task Area Home](README.md) | [Next: Next Task →](Next_Task.md)
```

Navigation rules:

- **Previous** returns to the preceding task in the documented workflow.
- **Home** returns to the task-area `README.md` portal.
- **Next** moves to the next task or reference in the documented workflow.
- The top and bottom navigation should use the same destinations.
- Do not force a false linear sequence where the workflow branches.
- Manager-only procedures should not be inserted into the normal volunteer previous/next sequence unless the workflow actually requires a manager handoff.

## Print and Hard-Copy Usability

Operator procedures should be usable both digitally and as printed hard copies when practical.

A printed procedure cannot depend on clickable navigation to explain the task. The core instructions needed to perform the task must appear in the procedure itself.

For procedures likely to be printed:

- use a clear task title;
- state the purpose and intended audience;
- list anything required before starting;
- keep numbered actions in the order performed;
- make warnings and required values easy to find;
- state what successful completion looks like;
- keep essential instructions complete even when links are unavailable on paper;
- place Related Documents at the end for digital navigation and follow-up work.

Screenshots may be used when they materially help the operator identify a screen, field, or action, but a procedure should not become unusable solely because a screenshot prints poorly or is unavailable.

## Required Document Control

Every current SOP should begin with a short Document Control table using these exact field names:

| Document Control | Value |
|---|---|
| Document Type | Operational SOP |
| System | Name of the system or subsystem |
| Task | Short description of the operator task |
| Audience | Intended operator or volunteer group |
| Status | CURRENT, DRAFT, or RETIRED |
| Owner | Person or role responsible for the procedure |
| Last Reviewed | YYYY-MM-DD |
| Keywords | Comma-separated search terms |

### Status Rules

- `CURRENT` — approved procedure for present use.
- `DRAFT` — being written or tested; not yet the authoritative operator procedure.
- `RETIRED` — retained only when there is a reason to preserve it outside the archive.

Superseded procedures should normally be moved to the archive rather than left mixed with current operator instructions.

## Required SOP Structure

Use the sections below when they apply. Do not add empty sections merely to satisfy the template.

### 1. Purpose

State what the task accomplishes and when the operator would use the procedure.

### 2. Before You Start

List prerequisites that matter to the operator, such as required access, information, physical items, or another task that must already be complete.

Do not include engineering prerequisites the operator does not need to know.

### 3. Procedure

Write numbered steps in the order the task is actually performed.

- One operator action per step whenever practical.
- Use the labels and names the operator sees on screen.
- Use **bold** for buttons, fields, menu entries, and required values when it improves scanning.
- Explain why only when the explanation prevents a likely mistake.
- Do not bury required actions inside long paragraphs.

### Operator Language

Use the exact system or interface term when the operator needs to recognize it on screen, but explain what it means in plain language the first time the meaning matters.

### 4. Expected Result

Tell the operator how to recognize successful completion.

### 5. If Something Is Wrong

Include only likely failure conditions and the safe next action. Link to a troubleshooting procedure when troubleshooting becomes substantial.

### 6. Related Documents

Link to related operator procedures and, when useful, the responsible engineering subsystem. Do not duplicate engineering detail in the SOP.

## Naming SOP Files

Use a descriptive task name that tells the reader what the procedure accomplishes.

Do not depend on a letter or number prefix to explain what the file contains.

## Portal and Indexing Requirements

When adding a new current SOP:

1. Place it under the correct operator/procedure area for the repository.
2. Add or update that task area's `README.md` so the procedure is directly discoverable.
3. Use the required Document Control fields.
4. Use a clear H1 title and descriptive filename.
5. Add meaningful `Keywords` for likely operator searches.
6. Verify all relative links and images.
7. Keep engineering detail in the responsible engineering documents and link to it when useful.
8. Keep the normal operator browse path operational; place engineering links in a separate related-information section rather than the task-selection table.
9. For multi-step workflow documentation, add previous/home/next navigation at both the top and bottom of each task procedure.

## Writing Goal

A volunteer should be able to open the procedure, understand whether it is the right procedure, and begin the task without first learning the underlying system architecture.
