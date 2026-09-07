# Runbook-First Production Rule

| Document Control | Value |
|---|---|
| Status | CURRENT |
| Scope | Production deployments, server changes, service changes, firewall/proxy changes, database migrations, recovery actions, and other Production mutations |

## Mandatory Gate

**Production mutation commands are forbidden until the governing runbook has been retrieved from the responsible repository and read in the current workstream.**

Chat history, model memory, summaries, remembered commands, or a previously used procedure do not satisfy this gate when a repository-owned runbook exists.

## Required Procedure

Before issuing any Production mutation command:

1. Identify the repository that owns the runtime or subsystem being changed.
2. Identify the governing runbook, deployment procedure, recovery procedure, or current runtime authority.
3. Retrieve and read that authority from the repository in the current workstream.
4. Compare it with current live runtime evidence when the current machine state may differ from the documentation.
5. State the governing authority before the mutation in this form:

```text
Authority: <repository> — <runbook/document>
Procedure: <documented section or accepted deployment pattern>
This step: <specific controlled action>
```

6. Issue only the single controlled mutation supported by that procedure.
7. Inspect the result before proceeding to another mutation.

## Runbook Fidelity

Commands must come from the governing runbook or be a narrowly parameterized adaptation of it. Acceptable substitutions include the intended service name, port, host, path, application prefix, version, or other target-specific value.

Do not invent a new deployment sequence, diagnostic sequence, rollback method, or retry procedure merely because the documented step is inconvenient or because a previous command failed.

Live evidence may override stale documentation for facts about the current runtime, but it does not remove the requirement to use the repository-owned procedure as the operating authority.

## Failure Rule

If a documented Production step fails:

1. Stop further mutation.
2. Preserve or execute the documented rollback/fail-closed behavior.
3. Re-read the governing runbook.
4. Compare the failure against prior accepted deployment or recovery evidence.
5. Determine whether the failure was an execution error, a changed live condition, or a documentation gap before proposing another mutation.

Do not immediately improvise a replacement procedure.

## Runbook Gap Rule

If the governing documentation does not cover the required situation, explicitly state:

```text
RUNBOOK GAP FOUND
```

Then identify the exact missing, stale, or contradictory instruction. Gather read-only evidence as needed and update the responsible repository documentation before later Production work depends on the new procedure.

A runbook gap is not permission to silently substitute an ad hoc process.

## Cross-Repository Systems

When a Production change crosses repository boundaries, use each repository for the facts it owns. For example:

- application repository — application source and application deployment contract;
- Production Database repository — schema, migrations, data/business rules;
- Server Management repository — host runtime, services, ports, mounts, firewall, proxy, recovery;
- Internal Web Backbone repository — intranet navigation/presentation deployment owned by that project.

Identify all governing authorities needed for the specific mutation. Do not let one repository's documentation silently replace another repository's ownership.

## Durable Closeout

Accepted Production changes, failures that alter future procedure, rollback facts, and newly discovered runtime dependencies must be promoted into the responsible repository documentation before later work depends on them.

The repository, not the conversation, is the durable authority.

## Meaning of “Read the Project Instructions”

When Greg says **read the project instructions**, read `System_Documentation/Project_Rules/README.md` and all linked rules relevant to the requested work. For any Production mutation, this Runbook-First Production Rule is always relevant and mandatory.