# MSB Label Print Service — Failed Batch and Runtime Recovery

| Document Control | Value |
|---|---|
| Document Type | Operational SOP |
| System | MSB Label Print Service / PRINT-SERVER |
| Audience | MSB Database Administrator / Print Server Maintainer |
| Status | CURRENT |
| Owner | MSB Database Administrator |
| Initial Revision | 2026-08-27 |
| Last Reviewed | 2026-08-27 |
| Keywords | failed batch, retry blocked, label service, start, stop, status, live log, printer preflight, template, recovery, PostgreSQL, psql |

## Purpose

Use this procedure when the Label Print Service stops printing because a `FAILED` batch exists, when the scheduled background service must be started or stopped manually, or when the runtime cannot find an expected Brother `.lbx` template.

This procedure exists so recovery does not depend on chat history or an external assistant.

## Critical Safety Rule

The Label Print Service intentionally blocks automatic retry when a newer `FAILED` batch exists. This is the print-storm protection added after the repeated-print incident.

Do **not** delete or retry a failed batch until you know whether any physical labels were printed.

If physical printing may have started, if a Windows print job remains queued, or if any batch item has `printed_flag = true` / a non-null `printed_at`, stop and reconcile the physical labels before retrying. Do not simply delete the batch and restart the service.

## 1. Check Whether the Service Is Running

On `PRINT-SERVER`:

```powershell
Get-ScheduledTask -TaskName "MSB Label Service" |
    Select-Object TaskName,State

Get-ScheduledTaskInfo -TaskName "MSB Label Service" |
    Format-List LastRunTime,LastTaskResult

Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq 'python.exe' } |
    Select-Object ProcessId,ExecutablePath,CommandLine |
    Format-List
```

The expected production command line is:

```text
C:\Program Files\Python\python.exe C:\MSB_LabelService\label_poll_service_v3.py
```

Do not start a second copy if that process is already running.

## 2. View the Service Status / Live Log

The unattended Scheduled Task does not provide the old visible console window. Use the log as the runtime status display.

Recent activity:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Tail 100
```

Follow the log live:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Wait -Tail 30
```

Healthy idle output repeats every 15 seconds:

```text
Poll tick - checking for pending labels.
Pending labels - displays=0 containers=0
No pending labels. Service idle.
```

A blocked retry appears as:

```text
FAILED batch exists - blocking retry. display_batch_id=<id> container_batch_id=<id-or-None>
FAILED batch exists - manual intervention required.
```

## 3. Stop the Label Service for Recovery

Preferred Scheduled Task stop:

```powershell
Stop-ScheduledTask -TaskName "MSB Label Service"
```

Verify the Label Service Python process is gone:

```powershell
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -like '*C:\MSB_LabelService\label_poll_service_v3.py*'
    } |
    Select-Object ProcessId,CommandLine
```

If an interactive/manual service copy is running in a console, use `Ctrl+C` in that console.

Do not kill unrelated Python processes such as the independently deployed LOR runner.

## 4. Check the Windows Print Queue Before Any Failed-Batch Recovery

```powershell
Get-PrintJob -PrinterName "Brother PT-P950NW" |
    Format-Table ID,DocumentName,JobStatus,SubmittedTime -AutoSize
```

For a failed-before-print recovery, this must show no unresolved job associated with the failed batch.

If a job is present, do not delete the PostgreSQL failed batch yet.

## 5. Enter PostgreSQL Before Running SQL

The PostgreSQL server runs in the `msb-postgres` Docker container on `msb-prod-db` (`192.168.5.9`). SQL statements cannot be pasted directly at the Linux shell prompt.

From `PRINT-SERVER`, connect to the database host:

```powershell
ssh msbadmin@192.168.5.9
```

Enter the authorized `msbadmin` SSH password when prompted.

After login, the prompt will look similar to:

```text
msbadmin@msb-prod-db:~$
```

That is a **Linux shell**, not PostgreSQL. Do not paste `SELECT`, `DELETE`, `BEGIN`, or other SQL at that prompt.

Enter the PostgreSQL client using the command documented by the MSB Server Management repository:

```bash
docker exec -it msb-postgres psql -U msbadmin -d msb
```

A successful connection changes the prompt to a PostgreSQL prompt similar to:

```text
msb=#
```

Only after the `msb=#` prompt appears should the SQL in the following sections be entered.

Useful `psql` commands:

```text
\conninfo     show the current database/session
\q            exit psql and return to the Linux shell
```

To leave the Linux SSH session after exiting `psql`:

```bash
exit
```

## 6. Inspect the Failed Display Batch

At the `msb=#` PostgreSQL prompt, replace `<batch_id>` with the blocked Display batch ID shown in the service log.

```sql
SELECT
    b.display_label_batch_id,
    b.batch_started_at,
    b.batch_completed_at,
    b.status,
    b.started_by_person_id,
    b.started_by_text,
    b.notes
FROM ops.display_label_batch b
WHERE b.display_label_batch_id = <batch_id>;

SELECT
    i.display_label_batch_item_id,
    i.display_label_batch_id,
    i.display_id,
    i.display_name,
    i.printed_flag,
    i.printed_at,
    i.qr_url,
    i.line1,
    i.line2,
    d.print_label AS current_print_request
FROM ops.display_label_batch_item i
JOIN ref.display d
  ON d.display_id = i.display_id
WHERE i.display_label_batch_id = <batch_id>
ORDER BY i.display_label_batch_item_id;
```

### Safe failed-before-print signature

A failed batch may be retired for clean retry only when all of the following are true:

- header status is `FAILED`;
- no physical labels from that batch printed;
- Windows print queue has no unresolved job from that batch;
- every batch item has `printed_flag = false`;
- every batch item has `printed_at IS NULL`;
- the intended Displays still have `ref.display.print_label = true` if they are supposed to retry.

If any of those conditions are not true or cannot be proven, do not use the delete/retry procedure below.

## 7. Retire a Failed-Before-Print Display Batch and Preserve the Retry Request

The batch-item foreign key uses `ON DELETE CASCADE`, so deleting the failed header removes only that batch's snapshot items. It does **not** clear `ref.display.print_label`; that flag is cleared only by successful finalization.

At the `msb=#` prompt, use one transaction and the exact failed batch ID:

```sql
BEGIN;

DELETE FROM ops.display_label_batch
WHERE display_label_batch_id = <batch_id>
  AND status = 'FAILED';

-- Must report exactly one deleted header row.

COMMIT;
```

Then verify:

```sql
SELECT *
FROM ops.display_label_batch
WHERE display_label_batch_id = <batch_id>;

SELECT
    display_id,
    display_name,
    print_label
FROM ref.display
WHERE print_label = true
ORDER BY display_id;
```

Expected result:

- the retired failed batch no longer exists;
- the intended Display requests remain `print_label = true`;
- the service is free to create a new snapshot batch when restarted.

### Do not use `confirm_last_batch.py` for this condition

`confirm_last_batch.py` finalizes a batch as successfully printed, writes print history, clears the snapshot rows' `print_label` flags, and marks the batch completed. It is not appropriate when printing never occurred.

### `fail_last_batch.py` is not the retry-unblock step

`fail_last_batch.py` marks an active batch `FAILED` while preserving selection flags. The production service then intentionally blocks newer work until the failed batch is manually reconciled. Do not run it expecting the service to resume automatically.

## 8. Container Failed-Batch Inspection

At the `msb=#` PostgreSQL prompt, use the corresponding Container queries when the service reports a failed container batch:

```sql
SELECT
    b.container_label_batch_id,
    b.batch_started_at,
    b.batch_completed_at,
    b.status,
    b.started_by_person_id,
    b.started_by_text,
    b.notes
FROM ops.container_label_batch b
WHERE b.container_label_batch_id = <batch_id>;

SELECT
    i.container_label_batch_item_id,
    i.container_label_batch_id,
    i.container_id,
    i.label_orientation,
    i.printed_flag,
    i.printed_at,
    i.qr_url,
    i.container_label,
    c.print_label AS current_print_request
FROM ops.container_label_batch_item i
JOIN ref.container c
  ON c.container_id = i.container_id
WHERE i.container_label_batch_id = <batch_id>
ORDER BY i.container_label_batch_item_id;
```

Only for a proven failed-before-print Container batch, retire it with:

```sql
BEGIN;

DELETE FROM ops.container_label_batch
WHERE container_label_batch_id = <batch_id>
  AND status = 'FAILED';

COMMIT;
```

The same safety rules apply: do not delete and retry if physical printing may already have occurred.

When database recovery is complete, leave PostgreSQL with `\q`, then leave the SSH session with `exit`.

## 9. Verify the Production Brother Template Runtime Paths

The source-controlled PT-P950NW templates currently live under:

```text
docs\01_Engineering\templates\pt_p950nw\
```

The production v3.4 runtime still expects deployed copies under:

```text
C:\MSB_LabelService\templates\
```

Required current files include:

```text
QR_display_labels_2_line.lbx
QR_container_horizontal.lbx
QR_container_vertical.lbx
```

Verify the runtime files:

```powershell
Get-ChildItem C:\MSB_LabelService\templates\*.lbx |
    Select-Object Name,FullName,Length,LastWriteTime
```

If source templates were reorganized in Git, do not assume the runtime path changed with them. Deployment must place the required `.lbx` files where the production configuration/service expects them.

A missing runtime template produces repeated preflight failures such as:

```text
Printer preflight failed: Could not open template: C:\MSB_LabelService\templates\QR_display_labels_2_line.lbx
```

This failure occurs before a new batch should be created by the current v3.4 preflight path.

## 10. Verify PT-P950NW Media Before Restart

The status-only SNMP diagnostic is under the repository test diagnostics. Run it from the deployed repository path:

```powershell
python .\tests\printer_diagnostics\pt950_snmp_status_probe.py
```

Known tested ready-state examples include:

```text
36 mm laminated: width 0x24, type 0x01
24 mm laminated: width 0x18, type 0x01
12 mm laminated: width 0x0C, type 0x01
```

Known tested failure/condition signatures include:

```text
36 mm cassette empty: width 0x24, type 0x01, Error Information 1 = 0x02 (end of media)
No cassette / cover closed: width 0x00, type 0x00
Cover open: Error Information 2 = 0x10; media identity is not reported while the cover is open
```

Use the actual tested printer response as the operational evidence; do not assume a cassette is ready merely because it is physically present.

## 11. Start the Label Service Again

Preferred unattended start:

```powershell
Start-ScheduledTask -TaskName "MSB Label Service"
```

Verify:

```powershell
Get-ScheduledTask -TaskName "MSB Label Service" |
    Select-Object TaskName,State

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -like '*C:\MSB_LabelService\label_poll_service_v3.py*'
    } |
    Select-Object ProcessId,ExecutablePath,CommandLine |
    Format-List
```

Then follow the log:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Wait -Tail 30
```

Expected retry sequence after a safe failed-before-print batch was retired:

```text
Pending labels - displays=<n> containers=<n>
Printer preflight passed: ...
Batch creation results - display_batch_id=<new id> ...
Batch rows committed before printing...
... physical print ...
Display batch <new id> completed successfully.
```

## 12. Interactive Manual Fallback Start

Use this only when the Scheduled Task is intentionally stopped and an administrator wants a visible console:

```powershell
Set-Location C:\MSB_LabelService
& "C:\Program Files\Python\python.exe" .\label_poll_service_v3.py
```

Stop the interactive copy with `Ctrl+C`.

Do not run an interactive copy at the same time as the Scheduled Task copy.

## 13. Recovery Decision Summary

```text
FAILED batch reported
    -> stop service
    -> inspect Windows print queue
    -> SSH to msb-prod-db
    -> enter psql inside msb-postgres
    -> inspect failed header/items and current print request flags
    -> determine whether physical printing occurred

    if printing definitely DID NOT occur:
        -> correct printer/template/media problem
        -> retire only that FAILED batch
        -> preserve print_label request
        -> restart service
        -> verify one fresh batch prints once

    if printing DID occur or may have occurred:
        -> DO NOT delete/retry blindly
        -> reconcile physical labels, spooler state, batch items, history, and request flags first
```

## Related Documents

- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md)
- [Operator Label Printing](Operator_Label_Printing.md)
- [Runtime Recovery — 2026-08-24](Label_Print_Service_Runtime_Recovery_2026-08-24.md)
- [Label Print Service Engineering Rules](../../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
- [MSB Server Management — PostgreSQL Server Commands](https://github.com/Gregovate/MSB-Server-Management/blob/main/docs/postgresql/Server%20Commands.md)

## Revision History

| Date | Change |
|---|---|
| 2026-08-27 | Added the missing end-to-end PostgreSQL entry procedure: SSH to `msb-prod-db`, enter `psql` inside the `msb-postgres` container, identify the `msb=#` prompt, and exit cleanly. This closes the gap that previously told an administrator to run SQL without saying how to enter PostgreSQL. |
| 2026-08-27 | Initial controlled recovery SOP. Added scheduled-task start/stop/status, live-log access for the background service, FAILED-batch inspection and safe failed-before-print retirement, source-vs-runtime template path contract, and tested PT-P950NW SNMP media checks. |
