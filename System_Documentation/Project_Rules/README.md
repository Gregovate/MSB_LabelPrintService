# Project Rules

This folder contains governance and working rules specific to `MSB_LabelPrintService`.

Reusable MSB documentation and engineering standards belong under [`../Standards/`](../Standards/README.md). Repository-specific rules belong here so the Label Print Service can add production/runtime safeguards without changing the shared standards used by other MSB projects.

## Current Project Rules

- [Label Print Service Engineering Rules](Label_Print_Service_Engineering_Rules.md) — governs source recovery, production-runtime inspection, database/service boundaries, print-storm safety, version control, deployment/rollback, spooler recovery, secrets, operator documentation, and mandatory engineering handoff maintenance.

## Rule Ownership

Use this folder for durable rules that apply to Label Print Service engineering but are not appropriate as reusable cross-repository standards.

Service implementation details, current runtime facts, and operator procedures belong in their responsible engineering or procedure documents rather than being duplicated here.
