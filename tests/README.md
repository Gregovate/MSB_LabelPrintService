# Tests

This tree contains non-production test and diagnostic code for `MSB_LabelPrintService`.

## Safety boundary

Code under `tests/` is not part of the deployed Label Print Service unless a later controlled engineering change explicitly promotes proven behavior into production source.

Test utilities must state whether they can print, write PostgreSQL state, modify Windows spooler state, or alter printer configuration.

Current printer diagnostics live under [`printer_diagnostics/`](printer_diagnostics/README.md).
