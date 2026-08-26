# MSB Label Print Server Runtime Runbook

| Document Control | Value |
|---|---|
| Document Type | Operational SOP |
| System | MSB Label Print Service / PRINT-SERVER |
| Task | Start, verify, remotely recover, and reboot-test PRINT-SERVER runtimes |
| Audience | MSB Database Administrator / Print Server Maintainer |
| Status | CURRENT |
| Owner | MSB Database Administrator |
| Last Reviewed | 2026-08-25 |
| Keywords | label print service, LOR runner, print server, PRINT-SERVER, Brother, PT-P950NW, b-PAC, SSH, OpenSSH, Task Scheduler, reboot, recovery |

## Purpose

This runbook documents the verified production startup and recovery procedure for the dedicated Windows Label Print Service host.

It exists so the Label Print Service can recover after a Windows reboot or update without requiring a user to log into the Beelink and manually start the service.

This is **not** the normal Directus label-request procedure. This document is for administrators maintaining the dedicated print-server runtime.

The Label Print Service remains the accepted production workload on this host.
Additional supporting runtimes must be documented and deployed independently;
they must not be folded into the Label Print Service process, startup task,
configuration, logs, or recovery actions.

## Current Production Runtime

Verified on 2026-08-24:

```text
Windows hostname: PRINT-SERVER
IPv4: 192.168.5.56
Windows account: PRINT-SERVER\Print Service
Production working directory: C:\MSB_LabelService
Production Python: C:\Program Files\Python\python.exe
Current service script: C:\MSB_LabelService\label_poll_service_v3.py
Service version: 3.4
Legacy manual launcher: C:\start_label_service.bat
Brother printer queue: Brother PT-P950NW
Brother printer port: 192.168.5.12_1
```

Do not record the Windows account password or `config.local.ini` secrets in Git.

## `Print Service` Account and Credential Contract

The verified Windows runtime account is:

```text
PRINT-SERVER\Print Service
SID: S-1-5-21-985230857-1861968803-3831776692-1003
```

Direct verification on 2026-08-25 returned:

```text
Enabled               : True
PasswordRequired      : False
UserMayChangePassword : True
```

`PasswordRequired: False` means the local account policy does not require a
password. It does **not** prove that the account currently has a blank
password and it does not authorize creating a production task without the
account credential.

The accepted `MSB Label Service` task uses:

```text
UserId    : Print Service
LogonType : Password
RunLevel  : Highest
```

[Windows Task Scheduler requires the account password](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type)
when a task is registered with `LogonType: Password`. This logon type is what
allows the task to run before an interactive Windows login while retaining the
user account's normal resource access.

Credential handling rules:

- As verified on 2026-08-25, the current credential record is an onsite
  physical label at the PRINT-SERVER workstation. The runbook records that
  retrieval method but must never reproduce the password value.
- Do not place the password in Git, Markdown, PowerShell scripts, task XML,
  tickets, chat transcripts, or deployment logs.
- Retrieve and verify the existing credential before creating or updating a
  password-logon Scheduled Task.
- Do not reset the account password merely because it is unavailable to the
  current maintainer. A reset can invalidate credentials stored by existing
  Scheduled Tasks and can affect other user-profile-protected runtime data.
- Any controlled password change must include updating and retesting every
  dependent task, SSH access, protected credential, and post-reboot runtime.

The no-password `S4U` task mode is not an equivalent substitute. The same
Microsoft Task Scheduler reference documents that an S4U task has no network
access and no access to encrypted files. Do not use S4U for the LOR runner
unless engineering validation proves that all Google Drive, PostgreSQL,
runner-state, and DPAPI-protected resources remain available in that exact
task context.

## Production LOR Runner Host — Accepted 2026-08-25

The permanent LOR operator runner is deployed on this host:

```text
Rollback/test host: MSB-OFFICE-PC (192.168.5.55), listener disabled
Production host: PRINT-SERVER (192.168.5.56)
Production account: PRINT-SERVER\Print Service
Production directory: C:\MSB_LORRunner
Scheduled Task: MSB LOR Operator Runner
Runner: V1.6.0
Deployment status: PRODUCTION ACCEPTED
```

The Office Desktop was suitable only for initial testing. Closing its
PowerShell window stopped the runner and left LOR2DB unable to start
parser/version operations even though PostgreSQL and the Linux API remained
healthy.

PRINT-SERVER cutover passed local health, restricted TCP reachability,
controlled Linux pairing, authenticated API-to-runner health, dashboard
availability, controlled parser V7.0.11, PostgreSQL ingest 55, reconciliation
Run 13, immutable report publication, and final production Display
verification. The existing Label Print Service task and process remained
separate and running.

The LOR runner must be deployed as a separate PRINT-SERVER runtime with its
own:

- Scheduled Task, expected name `MSB LOR Operator Runner`;
- process and working directory;
- Python environment and reviewed Production Database repository release;
- DPAPI-protected runner token and PostgreSQL ingest credential created under
  the permanent task account;
- TCP 8791 listener and firewall rule restricted to `192.168.5.9`;
- service log, parser/ingest operation records, and recovery procedure; and
- restart-on-failure behavior that cannot create concurrent runner instances.

The existing `MSB Label Service` task, `C:\MSB_LabelService` deployment,
Brother configuration, printing credentials, logs, and spooler recovery must
remain unchanged and operationally independent.

### Google Drive Cold-Boot Finding — INITIAL PROBE WAS A FALSE POSITIVE

A temporary Password-logon Session-0 task initially reported
`GDrivePresent=True` and found every required LOR `G:` path. That task ran
while an interactive desktop session had already mounted Google Drive. It did
not prove that the mapping existed after a cold boot without login.

The first true reboot showed the actual boundary:

```text
PRINT-SERVER ping/SSH: available
MSB Label Service: Running
Google Drive G:\: absent
MSB LOR Operator Runner: Ready / LastTaskResult 1
TCP 8791: no listener
runner log: runner-state.json not found
```

Launching Google Drive for Desktop in Session 0 created processes but did not
mount `G:`; path checks could hang. Google Drive for Desktop requires an
interactive `Print Service` session in this deployment.

The accepted production control is Microsoft Sysinternals Autologon for
`PRINT-SERVER\Print Service`. The host is physically controlled. The
credential is stored as an LSA secret and is not recorded in Git, but local
administrators can recover it. This is a deliberate availability/security
tradeoff.

After Autologon was enabled, reboot restored the desktop session, Google Drive
`G:`, the LOR task/listener, authenticated Linux API access, and dashboard
health. The Label Print Service remains independently capable of starting
without login; only the LOR runner depends on the interactive Google Drive
mount.

Runner V1.6.0 and the `PrintServerUnattended` deployment profile were merged
into the Production Database repository by
[PR 74](https://github.com/Gregovate/MSB-Production-Database-Project/pull/74).
The implementation enforces the correct host and account, creates a separate
at-startup Password-logon task with a one-minute delay, defaults to
`192.168.5.56:8791`, and preserves the Office interactive profile for rollback.

### Accepted Deployment Evidence

1. The reviewed Production Database repository was cloned into
   `C:\MSB_LORRunner` at merged commit `2d89620`.
2. An isolated virtual environment was created and 40 parser/runner tests
   passed.
3. The LOR firewall rule permits TCP 8791 only from `192.168.5.9` on the
   Private profile and only for the isolated runner Python executable.
4. The task uses `Print Service`, Password logon, Highest, an at-startup
   trigger, and a one-minute delay.
5. Account-bound DPAPI runner and PostgreSQL credentials were created under
   the Print Service account.
6. Pairing used the exact reviewed installer staged separately on Linux; the
   protected `/opt/fieldwiring` checkout was not modified.
7. The initial headless-path conclusion was rejected after cold-boot testing.
8. Sysinternals Autologon was enabled so Google Drive could mount `G:`.
9. A second reboot, controlled parser, ingest 55, and reconciliation Run 13
   passed.

### Cutover Acceptance — PASSED WITH RECORDED GOOGLE DRIVE DEPENDENCY

Passed:

- local authenticated runner V1.6.0 health;
- TCP 8791 reachability from `msb-prod-db`;
- matching protected-token fingerprint after controlled re-pairing;
- authenticated Linux API-to-runner request;
- LOR2DB dashboard availability;
- controlled parser V7.0.11 and exact SQLite digest verification;
- PostgreSQL ingest 55 and reconciliation Run 13 validation;
- automatic-login reboot recovery of Google Drive and the LOR listener;
- independent Label Service and LOR task/process/working-directory boundaries;
- old MSB-OFFICE-PC listener disabled.

The Label Print Service's earlier unattended physical-print acceptance remains
valid because its task, Python, configuration, and printer path were unchanged.
A separate post-LOR-cutover physical label was not recorded during this
incident.

Known limitation: the LOR task can check prerequisites before Google Drive has
finished mounting `G:` and then exit. Engineering must add bounded readiness
retry or an equivalent startup dependency. Until fixed, verify `G:` before
starting one replacement managed instance.

The runner implementation, parser/ingest contract, Linux pairing, and LOR2DB
operator recovery remain owned by
[`Gregovate/MSB-Production-Database-Project`](https://github.com/Gregovate/MSB-Production-Database-Project).
This runbook owns the PRINT-SERVER host/runtime boundary and the requirement
that the two production workloads remain independently recoverable.

## Normal Startup Model

The accepted Label Print Service startup model remains:

```text
Windows boot/reboot
    -> Windows Print Spooler starts automatically
    -> OpenSSH Server starts automatically
    -> Scheduled Task "MSB Label Service" starts after boot
    -> C:\Program Files\Python\python.exe
       C:\MSB_LabelService\label_poll_service_v3.py
    -> Label Service performs its startup health check
    -> Label Service polls PostgreSQL every 15 seconds
    -> Brother b-PAC submits print jobs
    -> Windows spooler verifies completion
    -> Brother PT-P950NW prints labels
```

**No interactive Windows desktop login is required for normal Label Print Service operation.**

The LOR runner has a different dependency:

```text
Windows boot
    -> Sysinternals Autologon signs in Print Service
    -> Google Drive for Desktop mounts G:
    -> MSB LOR Operator Runner starts or is restarted after G: is ready
    -> 192.168.5.56:8791 becomes available to msb-prod-db
```

Do not describe the LOR runtime as pre-login/headless while it depends on this
interactive Google Drive mount.

## Historical Manual Launcher

The legacy desktop launcher remains available as a fallback:

```text
C:\start_label_service.bat
```

Contents verified on 2026-08-24:

```bat
@echo off
color 1E
title MSB LABEL SERVICE - DO NOT CLOSE
cd /d C:\MSB_LabelService
"C:\Program Files\Python\python.exe" label_poll_service_v3.py
pause
```

This launcher is interactive and was the former normal startup method. Before the unattended startup change, a user had to log into Windows and manually start it after a reboot.

Do not use the batch file as the Scheduled Task action. The scheduled task launches Python directly.

## Verified Original Reboot Failure Mode

Before the 2026-08-24 correction:

```text
Windows reboot/update
    -> Windows reached sign-in screen
    -> Print Spooler started normally
    -> Brother PT-P950NW queue was present and Normal
    -> Label Print Service did NOT start
    -> user had to log into Windows
    -> user manually started C:\start_label_service.bat
```

Read-only inspection found no Label Print Service startup entry in:

- Task Scheduler;
- the all-users Startup folder;
- the `Print Service` user Startup folder;
- `HKLM\Software\Microsoft\Windows\CurrentVersion\Run`;
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

The failure was therefore a missing unattended startup mechanism, not a broken existing one.

## OpenSSH Remote Administration

Microsoft OpenSSH Server was installed and enabled on `PRINT-SERVER` on 2026-08-24.

Verified state:

```text
OpenSSH.Client~~~~0.0.1.0 : Installed
OpenSSH.Server~~~~0.0.1.0 : Installed
sshd service              : Running / Automatic
Firewall rule              : OpenSSH-Server-In-TCP enabled
TCP 22                     : listening on 0.0.0.0 and ::
```

### Install / Enable OpenSSH Server

Run from an elevated PowerShell session on `PRINT-SERVER`:

```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'

Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

Verify:

```powershell
Get-Service sshd | Select-Object Name,Status,StartType

Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Select-Object Name,Enabled,Direction,Action

Get-NetTCPConnection -LocalPort 22 -State Listen |
    Select-Object LocalAddress,LocalPort,State,OwningProcess
```

### Connect From MSB-Office-PC

Because the account name contains a space, use `-l`:

```powershell
ssh -l "Print Service" 192.168.5.56
```

Verify the remote host and account:

```cmd
hostname
whoami
```

Expected:

```text
PRINT-SERVER
print-server\print service
```

### Verified Pre-Login SSH Recovery

On 2026-08-24, `PRINT-SERVER` was rebooted and intentionally left at the Windows sign-in screen. Nobody logged into the desktop.

OpenSSH returned automatically and accepted a remote login as `PRINT-SERVER\Print Service`.

This proves SSH recovery is available after reboot without an interactive Windows login.

## Verified Pre-Login Printer State

After reboot, before anyone logged into the Windows desktop:

```text
explorer.exe: not running
python.exe: not running before service start
Windows Spooler: Running / Automatic
Brother PT-P950NW queue: Normal
Brother port: 192.168.5.12_1
```

The Windows print infrastructure therefore returns at boot independently of an interactive desktop.

## Headless Service Verification

Before creating the scheduled task, the existing production service was started through SSH while the Beelink remained at the Windows sign-in screen:

```cmd
cd /d C:\MSB_LabelService
"C:\Program Files\Python\python.exe" label_poll_service_v3.py
```

The v3.4 startup health check passed, including:

- PostgreSQL connection to database `msb`;
- PostgreSQL login `printservice`;
- reads from `ref.display` and `ref.container`;
- temporary write test;
- `ref.person` match for PrintService;
- `ref.resolve_actor()`;
- normal 15-second polling.

A real Container label request physically printed successfully while the machine remained at the Windows sign-in screen.

This proved that the Label Print Service, PostgreSQL access, Brother b-PAC path, Windows spooler, and PT-P950NW do not require an interactive Windows desktop.

## Scheduled Task Configuration

The production Scheduled Task is named:

```text
MSB Label Service
```

Verified principal:

```text
UserId    : Print Service
LogonType : Password
RunLevel  : Highest
```

Configure it to **Run whether user is logged on or not**.

### Trigger

Use an **At startup** trigger with a one-minute startup delay.

The delay gives Windows networking, the print spooler, and the Brother stack time to initialize before the Python startup health check runs.

### Action

Use these values in **Task Scheduler -> MSB Label Service -> Properties -> Actions**.

**Program/script**

```text
C:\Program Files\Python\python.exe
```

Task Scheduler may display quotation marks around this field after the executable is selected with **Browse**. That is acceptable.

**Add arguments**

```text
C:\MSB_LabelService\label_poll_service_v3.py
```

Quotation marks around this argument are acceptable.

**Start in**

```text
C:\MSB_LabelService
```

**Do not place quotation marks in the Start in field.**

### Recommended Task Settings

Use:

```text
Run whether user is logged on or not
Run with highest privileges
Allow task to be run on demand
Run task as soon as possible after a scheduled start is missed
If the task is already running: Do not start a new instance
```

Do not configure a normal execution-time limit that stops this long-running service after a fixed number of hours or days.

If task restart-on-failure settings are used, they must not create multiple concurrent service instances.

## Scheduled Task Troubleshooting

### `0x8007052E` — User Name or Password Is Incorrect

Observed while attempting to register a separate headless path-probe task:

```text
Register-ScheduledTask : The user name or password is incorrect.
FullyQualifiedErrorId  : HRESULT 0x8007052e
```

This means Task Scheduler rejected the supplied account credential. The task
was not created. Later `Start-ScheduledTask`, `Get-ScheduledTask`, and
`Get-ScheduledTaskInfo` errors for that task are expected consequences and do
not indicate additional failures.

Required response:

1. Stop dependent commands; do not repeatedly guess passwords.
2. Confirm the current identity with `whoami`.
3. Confirm the exact local account with `Get-LocalUser -Name "Print Service"`.
4. Retrieve the existing `PRINT-SERVER\Print Service` credential from the
   authorized onsite physical record at the PRINT-SERVER workstation.
5. Do not reset the account or modify `MSB Label Service` as a shortcut.
6. Retry only after the exact account and credential have been confirmed.

The failed probe did not change the production `MSB Label Service` task.

### `2147942402` — File Not Found

Observed bad action:

```text
Execute          : C:\Program
Arguments        : Files\Python\python.exe C:\MSB_LabelService\label_poll_service_v3.py
```

Observed result:

```text
LastTaskResult : 2147942402
```

This is `0x80070002` / file not found. Windows attempted to execute `C:\Program`.

Fix: keep the Python executable in **Program/script** and the service script in **Add arguments**.

### `2147942667` — Directory Name Invalid

Observed bad action:

```text
Execute          : "C:\Program Files\Python\python.exe"
Arguments        : "C:\MSB_LabelService\label_poll_service_v3.py"
WorkingDirectory : "C:\MSB_LabelService"
```

Observed result:

```text
LastTaskResult : 2147942667
```

This is `0x8007010B` / directory name invalid.

Fix: remove quotation marks from **Start in** so it is exactly:

```text
C:\MSB_LabelService
```

## Verify the Scheduled Task Is Running

From SSH:

```cmd
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'MSB Label Service' | Select-Object TaskName,State | Format-List"
```

Expected:

```text
TaskName : MSB Label Service
State    : Running
```

Check the task result:

```cmd
powershell -NoProfile -Command "Get-ScheduledTaskInfo -TaskName 'MSB Label Service' | Format-List LastRunTime,LastTaskResult"
```

For a continuously running task, this was verified as:

```text
LastTaskResult : 267009
```

`267009` is `0x41301`, meaning the task is currently running.

Check the actual Python process:

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
```

Expected executable and command line:

```text
ExecutablePath : C:\Program Files\Python\python.exe
CommandLine    : "C:\Program Files\Python\python.exe" "C:\MSB_LabelService\label_poll_service_v3.py"
```

## Verify Service Polling

Check the live service log:

```cmd
powershell -NoProfile -Command "Get-Content 'C:\MSB_LabelService\logs\label_service.log' -Tail 30"
```

Healthy idle behavior repeats every 15 seconds:

```text
Poll tick - checking for pending labels.
Pending labels - displays=0 containers=0
No pending labels. Service idle.
```

## Physical Print Acceptance

The Scheduled Task execution context was tested on 2026-08-24 with a real Display label request.

The Display label physically printed successfully through:

```text
Scheduled Task
    -> Python v3.4
    -> PostgreSQL
    -> Brother b-PAC
    -> Windows print spooler
    -> Brother PT-P950NW
    -> physical Display label
```

This confirms the task's noninteractive execution context can use the production Brother printing stack.

## Reboot Acceptance — PASSED 2026-08-24

Final unattended reboot acceptance passed on 2026-08-24.

Test conditions:

1. `PRINT-SERVER` was rebooted.
2. No user logged into the Windows desktop to start the Label Print Service.
3. OpenSSH returned after reboot.
4. The `MSB Label Service` Scheduled Task started the production Python service.
5. The service resumed normal operation.
6. A real label request was submitted after reboot.
7. The physical label printed successfully.

This establishes the accepted production recovery behavior:

```text
Windows Update/reboot
    -> no human Windows login required
    -> OpenSSH available for administration
    -> MSB Label Service scheduled task starts automatically
    -> PostgreSQL polling resumes
    -> b-PAC / spooler / PT-P950NW printing works
```

The original post-reboot manual-start reliability problem is therefore resolved by host/runtime configuration without changing `label_poll_service_v3.py`.

## Manual Fallback Start

If the scheduled task is intentionally stopped and an administrator needs an interactive fallback, use either the existing desktop launcher or run:

```cmd
cd /d C:\MSB_LabelService
"C:\Program Files\Python\python.exe" label_poll_service_v3.py
```

Do not start a manual copy if the Scheduled Task copy is already running.

Check first:

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
```

## Safe Reboot Verification Procedure

After a Windows Update or intentional reboot:

1. Do not immediately log into the Beelink desktop just to start the label service.
2. From `MSB-Office-PC`, verify SSH connectivity:

```powershell
Test-NetConnection 192.168.5.56 -Port 22
```

3. Connect:

```powershell
ssh -l "Print Service" 192.168.5.56
```

4. Verify the scheduled task:

```cmd
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'MSB Label Service' | Select-Object TaskName,State | Format-List"
```

5. Verify the Python process:

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
```

6. Verify fresh log polling:

```cmd
powershell -NoProfile -Command "Get-Content 'C:\MSB_LabelService\logs\label_service.log' -Tail 30"
```

7. If needed, submit one controlled label request and confirm the physical print.

## If Labels Are Not Printing After Reboot

Do not repeatedly request labels.

Check in this order:

1. SSH access to `192.168.5.56`.
2. `MSB Label Service` task state.
3. Python process command line.
4. recent `label_service.log` entries.
5. Windows Print Spooler state.
6. Brother PT-P950NW queue state.
7. PostgreSQL batch/request state before any destructive print recovery.

Verify the spooler:

```cmd
powershell -NoProfile -Command "Get-Service Spooler | Select-Object Name,Status,StartType | Format-List"
```

Verify printers:

```cmd
powershell -NoProfile -Command "Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus | Format-Table -AutoSize"
```

Expected production printer:

```text
Brother PT-P950NW    Brother PT-P950NW    192.168.5.12_1    Normal
```

## Destructive Spooler Recovery

`killspooler.bat` and `killspooler.ps1` are destructive recovery utilities because they discard queued Windows print jobs.

Do not use them as normal startup behavior.

Before clearing the spooler:

- determine what jobs are queued;
- determine the corresponding PostgreSQL batch/request state;
- confirm that queued jobs may safely be discarded;
- plan how duplicate physical printing will be avoided afterward.

## Related Documents

- [Repository README](../readme.md)
- [Runtime Recovery — 2026-08-22](Label_Print_Service_Runtime_Recovery_2026-08-22.md)
- [How the Label Service Works](How_Label_Service_Works.md)
- [Historical Operator Guide](Operator_Label_Printing.md)
- [Label Print Service Engineering Rules](../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
- [LOR Runner Operations and Disaster Recovery](https://github.com/Gregovate/MSB-Production-Database-Project/blob/main/LOR2DB/Application/Office_PC_Runner_Operations_and_Disaster_Recovery.md)
- [LOR Routine Display Maintenance and PRINT-SERVER Cutover Incident — 2026-08-25](https://github.com/Gregovate/MSB-Production-Database-Project/blob/main/LOR2DB/Application/LOR_Routine_Display_Maintenance_and_PRINT_SERVER_Cutover_Incident_2026-08-25.md)

## Revision History

| Date | Change |
|---|---|
| 2026-08-25 | Corrected the false Session-0 Google Drive conclusion; recorded required Print Service autologon, completed V1.6.0 production cutover, reboot/parser/ingest/Run 13 acceptance, and the remaining G: readiness limitation. |
| 2026-08-25 | Recorded the initial Session-0 LOR path probe and merged V1.6.0 `PrintServerUnattended` deployment implementation; later cold-boot testing superseded the headless conclusion. |
| 2026-08-25 | Corrected the credential-retrieval record: the current authorized source is an onsite physical label at the PRINT-SERVER workstation, not a password-manager entry. The password value remains excluded from Git. |
| 2026-08-25 | Added the verified `PRINT-SERVER\Print Service` account and credential contract, clarified that `PasswordRequired: False` does not prove a blank password, prohibited credential storage in Git, and documented the `0x8007052E` task-registration response. |
| 2026-08-25 | Recorded PRINT-SERVER as the approved permanent LOR runner host, explicitly marked the transfer as not yet deployed, and added prerequisite, isolation, cutover, reboot, and rollback gates. |
| 2026-08-24 | Created from direct `PRINT-SERVER` reconnaissance. Documented OpenSSH installation, verified pre-login operation, Scheduled Task configuration and troubleshooting, physical printing under Task Scheduler, and successful unattended reboot/physical-print acceptance. |
