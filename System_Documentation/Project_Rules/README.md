# Project Rules

This folder contains governance and working rules specific to `MSB_LabelPrintService`.

When Greg says **read the project instructions**, read this README and every linked rule relevant to the requested work before proposing changes.

## Mandatory Production Gate

**Production mutation commands are forbidden until the governing runbook has been retrieved from the responsible repository and read in the current workstream.**

For any Production deployment, print-service runtime change, scheduled-task/service change, configuration change, recovery action, or other Production mutation, the [Runbook-First Production Rule](Runbook_First_Production_Rule.md) is always relevant and mandatory.

Reusable MSB documentation and engineering standards belong under [`../Standards/`](../Standards/README.md). Repository-specific rules belong here so the Label Print Service can add production/runtime safeguards without changing the shared standards used by other MSB projects.

## Current Project Rules

- [Runbook-First Production Rule](Runbook_First_Production_Rule.md) — requires retrieving and reading the governing repository-owned runbook before any Production mutation command, stating the authority/procedure/current step, stopping after failures, and declaring `RUNBOOK GAP FOUND` rather than improvising when documentation is incomplete.
- [Label Print Service Engineering Rules](Label_Print_Service_Engineering_Rules.md) — governs source recovery, production-runtime inspection, database/service boundaries, print-storm safety, version control, deployment/rollback, spooler recovery, secrets, operator documentation, and mandatory engineering handoff maintenance.

## Rule Ownership

Use this folder for durable rules that apply to Label Print Service engineering but are not appropriate as reusable cross-repository standards.

Service implementation details, current runtime facts, and operator procedures belong in their responsible engineering or procedure documents rather than being duplicated here.
