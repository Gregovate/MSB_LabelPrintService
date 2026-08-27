# Printer Diagnostics

## Status

Engineering test harnesses only. Not production code.

## Purpose

This folder is for isolated Brother printer diagnostics that can be proven without importing or modifying the production `label_poll_service_v3.py` path.

The initial test target is the Brother PT-P950NW status response so cassette width, media type, tape/ribbon color, and media/error conditions can be observed directly before any production-service integration is attempted.

## PT-P950NW status probe

`pt950_status_probe.py` is deliberately status-only.

It:

- does **not** connect to PostgreSQL;
- does **not** import the production Label Print Service;
- does **not** use b-PAC;
- does **not** submit a Windows print job;
- does **not** send Raster, ESC/P, P-touch Template, cut, feed, or print commands;
- sends only the Brother `ESC i S` printer-status request (`1B 69 53`);
- expects the documented 32-byte PT-P950NW status response;
- logs both raw hexadecimal bytes and decoded fields.

The status packet decoding follows Brother's PT-P900/P900W/P950NW Raster Command Reference v1.02. The Brother manual documents the packet layout and media/error values; the TCP port number is runtime configuration and is therefore command-line configurable.

### Normal use

From the repository root on a machine that can reach the printer:

```powershell
python tests\printer_diagnostics\pt950_status_probe.py --host 192.168.5.12
```

If the printer's raw TCP port is not 9100, specify the actual port:

```powershell
python tests\printer_diagnostics\pt950_status_probe.py --host 192.168.5.12 --port <port>
```

Each successful response is also written as a timestamped text file under `results/`. The results directory is intentionally excluded from Git except for its `.gitignore`.

## Initial bench matrix

Run and retain results for at least:

1. known-good cassette currently used in production;
2. each available cassette width;
3. 12 mm cassette;
4. no cassette installed;
5. known empty cassette;
6. cover open with a cassette installed.

Do not infer that an empty cassette is equivalent to no cassette. The purpose of this test is to observe what the actual PT-P950NW reports for each physical state.

## Production safety

The Windows Print Spooler may remain running. During initial direct-printer diagnostics, keep the production Python polling service stopped so the test evidence is isolated from production activity.

Do not add print commands to the status probe. Any future direct-print experiment must be a separate explicitly named test program with its own safety documentation.
