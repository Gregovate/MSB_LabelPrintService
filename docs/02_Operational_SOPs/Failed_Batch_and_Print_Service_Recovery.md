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
| Keywords | failed batch, retry blocked, label service, start, stop, status, PostgreSQL, psql, live log, printer preflight, template, recovery |

## Purpose

Use this procedure when the Label Print Service stops printing because a `FAILED` batch exists, when the unattended service must be started or stopped, or when a runtime path/template/media problem prevents printing.

This procedure is written so recovery can be performed from the repository documentation without relying on chat history or an external assistant.

## Critical Safety Rule

The Label Print Service intentionally blocks automatic retry when a newer `FAILED` batch exists. This is print-storm protection.

**Do not retire/delete a failed batch until the cause of the failure has been corrected and you have proven that no physical labels from that batch printed.**

If the failed batch is retired before the underlying cause is corrected, the still-pending `print_label` requests can immediately create another batch and fail for the same reason. This occurred during the 2026-08-27 recovery: batch 355 was retired before the missing runtime CSV directory was restored, so batch 356 was created and failed for the same missing-directory condition. After the directory was restored and 356 was retired, batch 357 printed successfully.

If physical printing may have started, a Windows print job remains queued, or any batch item has `printed_flag = true` / non-null `printed_at`, stop and reconcile the physical labels before retrying.

### Physical label printed but the batch says FAILED

Do not apply the failed-before-print deletion procedure when the physical
label exists. This occurred with the first production Controller label on
2026-09-03: b-PAC returned successful `PrintOut`, `EndPrint`, and `Close`
results, but the short Windows job cleared before the old spooler watcher
started. Controller batch 1 was therefore falsely marked `FAILED` even though
`CTRL:1031` physically printed.

For this condition:

1. stop the service;
2. prove the Windows queue is empty;
3. inspect the exact failed header, frozen items, current request flags, and
   cached print history;
4. reconcile only the physically confirmed items as printed;
5. clear only their source requests and update their cached history once;
6. mark the exact batch completed while retaining both the original failure
   and recovery explanation;
7. verify zero pending requests and zero failed batches before restart.

Do not copy the Controller 1031 recovery SQL blindly. Every recovery must be
guarded by the actual batch/item IDs and inspected state so it cannot increment
history twice or clear an unrelated request.

## 1. Check Whether the Label Service Is Running

On `PRINT-SERVER` PowerShell:

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

Do not start a second Label Service instance.

## 2. Read the Service Log

Recent activity:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Tail 100
```

Live status:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Wait -Tail 30
```

A blocked retry appears as:

```text
FAILED batch exists - blocking retry. display_batch_id=<id> container_batch_id=<id-or-None>
```

Record the failed batch ID and the exact failure reason before changing anything.

## 3. Stop the Label Service During Recovery

If the Scheduled Task copy is running:

```powershell
Stop-ScheduledTask -TaskName "MSB Label Service"
```

If an interactive/manual copy is running, use `Ctrl+C` in that console.

Verify the Label Service process is gone:

```powershell
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'python.exe' -and
        $_.CommandLine -like '*C:\MSB_LabelService\label_poll_service_v3.py*'
    } |
    Select-Object ProcessId,CommandLine
```

Do not stop unrelated Python runtimes such as the LOR runner.

## 4. Check the Windows Print Queue

```powershell
Get-PrintJob -PrinterName "Brother PT-P950NW" |
    Format-Table ID,DocumentName,JobStatus,SubmittedTime -AutoSize
```

For a failed-before-print recovery, there must be no unresolved job associated with the failed batch. If a job exists, do not retire the PostgreSQL batch yet.

## 5. Enter PostgreSQL Correctly

SQL cannot be pasted directly at the Linux shell prompt.

From `PRINT-SERVER` PowerShell:

```powershell
ssh msbadmin@192.168.5.9
```

After authentication, the prompt is similar to:

```text
msbadmin@msb-prod-db:~$
```

That is a Linux shell, **not PostgreSQL**. Enter the PostgreSQL container/client:

```bash
docker exec -it msb-postgres psql -U msbadmin -d msb
```

The prompt must change to:

```text
msb=#
```

Optional verification:

```text
\conninfo
```

Only run the SQL below after the prompt is `msb=#`.

Exit PostgreSQL with:

```text
\q
```

Exit the SSH session with:

```bash
exit
```

The authoritative server-side PostgreSQL entry command is also maintained in `Gregovate/MSB-Server-Management`, `docs/postgresql/Server Commands.md`.

## 6. Inspect a Failed Display Batch

At `msb=#`, replace `<batch_id>` with the ID from the service log:

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

A batch is eligible for failed-before-print retirement only when all are true:

- header status is `FAILED`;
- no physical labels from that batch printed;
- Windows queue has no unresolved job from that batch;
- every item has `printed_flag = false`;
- every item has `printed_at IS NULL`;
- intended Displays still have `ref.display.print_label = true` for retry.

If any condition is uncertain, stop. Do not use the delete/retry procedure.

## 7. Correct the Failure **Before** Retiring the Batch

Read `notes` and the service log. Correct the actual cause first.

### Required runtime directories

The production runtime currently requires:

```text
C:\MSB_LabelService\csv\
C:\MSB_LabelService\templates\pt_p950nw\
C:\MSB_LabelService\templates\ql_820nwb\
C:\MSB_LabelService\state\
C:\MSB_LabelService\logs\
```

Verify:

```powershell
Test-Path C:\MSB_LabelService\csv
Test-Path C:\MSB_LabelService\templates\pt_p950nw
Test-Path C:\MSB_LabelService\templates\ql_820nwb
```

The `csv` directory is runtime-generated output used by the service. Template-design/test CSV files stored with source-controlled templates are separate artifacts and are not the production runtime CSV output.

### Current source-controlled template layout

The accepted root-level template organization is:

```text
templates\
  pt_p950nw\
    QR_display_labels_2_line.lbx
    QR_container_horizontal.lbx
    QR_container_vertical.lbx
  ql_820nwb\
    Code128_Rack_Horz.lbx
    QR_Rack_test.lbx
```

The duplicate templates currently under `docs\01_Engineering\templates\...` are temporary during the path/code transition and are intended to be removed after the production code/configuration uses the accepted root-level template paths.

Verify the P950 production templates:

```powershell
Get-ChildItem C:\MSB_LabelService\templates\pt_p950nw\*.lbx |
    Select-Object Name,FullName,Length,LastWriteTime
```

Do not retire the failed batch until the path named in the failure has been corrected.

## 8. Verify PT-P950NW Media Before Retry

Run the status-only diagnostic:

```powershell
Set-Location C:\MSB_LabelService
python .\tests\printer_diagnostics\pt950_snmp_status_probe.py
```

Known tested states:

```text
36 mm laminated ready: width 0x24, type 0x01
24 mm laminated ready: width 0x18, type 0x01
12 mm laminated ready: width 0x0C, type 0x01
36 mm cassette empty: width 0x24, type 0x01, error1 0x02
No cassette / cover closed: width 0x00, type 0x00
Cover open: error2 0x10; media identity is not reported while cover is open
```

Do not rely only on the physical appearance of the cassette.

## 9. Retire a Proven Failed-Before-Print Display Batch

Only after Sections 4–8 are satisfied:

```sql
BEGIN;

DELETE FROM ops.display_label_batch
WHERE display_label_batch_id = <batch_id>
  AND status = 'FAILED';

COMMIT;
```

Expected:

```text
DELETE 1
COMMIT
```

Verify the failed header is gone and the intended requests remain pending:

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

Deleting the failed header cascades only its snapshot batch items. Successful finalization—not this delete—is what clears the original `print_label` requests.

Do not use `confirm_last_batch.py` when printing did not occur. Do not use `fail_last_batch.py` expecting it to unblock retry; it creates/retains the `FAILED` state that intentionally blocks automatic retry.

## 10. Container Failed-Batch Recovery

Use the same sequence and safety gates. Inspect:

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
JOIN ref.container c ON c.container_id = i.container_id
WHERE i.container_label_batch_id = <batch_id>
ORDER BY i.container_label_batch_item_id;
```

Only for a proven failed-before-print Container batch, and only after correcting the cause:

```sql
BEGIN;
DELETE FROM ops.container_label_batch
WHERE container_label_batch_id = <batch_id>
  AND status = 'FAILED';
COMMIT;
```

## 11. Start the Service and Verify Exactly One Retry

Preferred unattended start:

```powershell
Start-ScheduledTask -TaskName "MSB Label Service"
```

For maintenance/recovery where a visible console is useful, keep the Scheduled Task stopped and use:

```powershell
Set-Location C:\MSB_LabelService
& "C:\Program Files\Python\python.exe" .\label_poll_service_v3.py
```

Do not run both copies.

Watch the log:

```powershell
Get-Content C:\MSB_LabelService\logs\label_service.log -Wait -Tail 30
```

Expected sequence:

```text
Pending labels - displays=<n> containers=<n>
Printer/runtime preflight passed
Created ... batch <new id>
Batch rows committed before printing
... physical print ...
Display batch <new id> completed successfully
Pending labels - displays=0 containers=0
```

## 12. 2026-08-27 Acceptance Evidence — Batches 355–357

The live incident established the required recovery order.

Batch 355 was `FAILED` with two Display items, both `printed_flag = false` and `printed_at = NULL`. Its failure was a missing runtime CSV path after repository reorganization.

Batch 355 was retired before the missing directory was actually restored. The service then passed printer preflight, created batch 356, committed its snapshot rows, and failed again at `write_csv()` with:

```text
FileNotFoundError: [Errno 2] No such file or directory:
'C:\MSB_LabelService\csv\display_labels.csv'
```

The service correctly blocked further retries on FAILED batch 356. After `C:\MSB_LabelService\csv\` was restored and 356 was retired, the service created batch 357. Batch 357 completed successfully and the next poll reported `displays=0 containers=0`.

This incident proves that **fixing the underlying runtime condition must occur before retiring the failed batch**.

## 13. Recovery Decision Summary

```text
FAILED batch reported
    -> stop Label Service
    -> inspect Windows print queue
    -> enter PostgreSQL correctly through msb-postgres / psql
    -> inspect failed header/items and current request flags
    -> identify exact failure cause
    -> CORRECT THE FAILURE
    -> verify template/runtime paths and printer/media

    if physical printing definitely DID NOT occur:
        -> retire only that FAILED batch
        -> preserve print_label request
        -> start one Label Service instance
        -> verify one fresh batch prints once
        -> verify pending count returns to zero

    if printing DID occur or may have occurred:
        -> DO NOT delete/retry blindly
        -> reconcile physical labels, spooler, batch items, history, and requests
```

## Related Documents

- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md)
- [Operator Label Printing](Operator_Label_Printing.md)
- [Runtime Recovery — 2026-08-24](Label_Print_Service_Runtime_Recovery_2026-08-24.md)
- `Gregovate/MSB-Server-Management/docs/postgresql/Server Commands.md`

## Revision History

| Date | Change |
|---|---|
| 2026-08-27 | Corrected recovery order from live batches 355–357: diagnose and correct the cause before retiring a failed batch; documented the repeated 356 failure and successful 357 acceptance; added explicit SSH -> Docker -> psql entry; aligned template documentation to root-level printer-specific folders and separated template-design CSVs from runtime-generated CSVs. |
| 2026-08-27 | Initial controlled recovery SOP. |
