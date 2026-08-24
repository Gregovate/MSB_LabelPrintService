# PRINT-SERVER SSH Remote Administration Runbook

| Document Control | Value |
|---|---|
| Document Type | Operational SOP |
| System | MSB Label Print Service / PRINT-SERVER |
| Task | Connect to, verify, reboot, and recover PRINT-SERVER through SSH |
| Audience | MSB Database Administrator / Print Server Maintainer |
| Status | CURRENT |
| Owner | MSB Database Administrator |
| Last Reviewed | 2026-08-24 |
| Keywords | SSH, OpenSSH, PRINT-SERVER, reboot, remote administration, label print service, Beelink |

## Purpose

Use this procedure to administer the dedicated Label Print Service host remotely from `MSB-Office-PC` without logging into the Beelink Windows desktop.

OpenSSH Server was installed and verified on `PRINT-SERVER` on 2026-08-24. It starts automatically with Windows and was successfully tested after reboot before any interactive Windows login.

Do not record the `Print Service` Windows password in Git, scripts, documentation, or chat transcripts.

## Current SSH Endpoint

```text
Host: PRINT-SERVER
IPv4: 192.168.5.56
Windows account: PRINT-SERVER\Print Service
SSH service: sshd
SSH port: TCP 22
sshd startup: Automatic
```

Because the Windows account name contains a space, use the SSH `-l` option rather than embedding the user name in `user@host` syntax.

## Connect From MSB-Office-PC

Open PowerShell on `MSB-Office-PC`.

### 1. Check TCP 22

```powershell
Test-NetConnection 192.168.5.56 -Port 22
```

Expected:

```text
TcpTestSucceeded : True
```

If TCP 22 is not reachable, do not assume the Label Print Service itself is the problem. The Windows host, network path, firewall, or `sshd` service may need investigation.

### 2. SSH Into PRINT-SERVER

```powershell
ssh -l "Print Service" 192.168.5.56
```

On the first connection from a workstation, OpenSSH may ask whether to trust the host key. After verifying that the destination is the MSB `PRINT-SERVER`, answer:

```text
yes
```

Enter the Windows password when prompted. The password is not displayed while typing.

### 3. Verify You Are on the Correct Machine

After login:

```cmd
hostname
whoami
```

Expected:

```text
PRINT-SERVER
print-server\print service
```

Do not run production-changing commands until the host identity is confirmed.

## Check the Label Print Service Through SSH

### Scheduled Task State

```cmd
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'MSB Label Service' | Select-Object TaskName,State | Format-List"
```

Healthy state:

```text
TaskName : MSB Label Service
State    : Running
```

### Scheduled Task Last Result

```cmd
powershell -NoProfile -Command "Get-ScheduledTaskInfo -TaskName 'MSB Label Service' | Format-List LastRunTime,LastTaskResult"
```

For the continuously running service, the accepted running result is:

```text
LastTaskResult : 267009
```

`267009` = `0x41301`, meaning the task is currently running.

### Python Process

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
```

Expected production command:

```text
ExecutablePath : C:\Program Files\Python\python.exe
CommandLine    : "C:\Program Files\Python\python.exe" "C:\MSB_LabelService\label_poll_service_v3.py"
```

### Service Log

```cmd
powershell -NoProfile -Command "Get-Content 'C:\MSB_LabelService\logs\label_service.log' -Tail 30"
```

Healthy idle polling repeats approximately every 15 seconds:

```text
Poll tick - checking for pending labels.
Pending labels - displays=0 containers=0
No pending labels. Service idle.
```

## Reboot PRINT-SERVER Through SSH

Use this only for an intentional reboot or approved maintenance/recovery action.

From the SSH session:

```cmd
shutdown /r /t 0
```

Meaning:

```text
/r   restart Windows
/t 0 restart immediately
```

The SSH session will disconnect as Windows shuts down. A message similar to this is normal:

```text
client_loop: send disconnect: Connection reset
```

That disconnect does not indicate an SSH failure.

## Reconnect After Reboot

The production `MSB Label Service` Scheduled Task has an approximately one-minute startup delay. Allow Windows enough time to boot and the task to start before declaring recovery failed.

### 1. Do Not Log Into the Beelink Just to Start the Service

Normal post-reboot operation does **not** require an interactive Windows desktop login.

### 2. Check SSH From MSB-Office-PC

After approximately 60-90 seconds:

```powershell
Test-NetConnection 192.168.5.56 -Port 22
```

Expected:

```text
TcpTestSucceeded : True
```

### 3. Reconnect

```powershell
ssh -l "Print Service" 192.168.5.56
```

### 4. Verify the Host

```cmd
hostname
whoami
```

Expected:

```text
PRINT-SERVER
print-server\print service
```

### 5. Verify Automatic Label Service Recovery

```cmd
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'MSB Label Service' | Select-Object TaskName,State | Format-List"
```

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe'} | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
```

```cmd
powershell -NoProfile -Command "Get-Content 'C:\MSB_LabelService\logs\label_service.log' -Tail 30"
```

Expected result:

- Scheduled Task is `Running`;
- `python.exe` is running `C:\MSB_LabelService\label_poll_service_v3.py`;
- log timestamps are newer than the reboot;
- normal polling has resumed.

## Verified Reboot Acceptance

This exact remote-reboot path was production-tested on 2026-08-24:

1. connected to `PRINT-SERVER` through SSH;
2. rebooted with `shutdown /r /t 0`;
3. left Windows without an interactive desktop login;
4. reconnected through SSH after boot;
5. confirmed the Label Print Service returned automatically;
6. submitted a real label request;
7. confirmed the physical label printed successfully.

This establishes SSH as a valid administration/recovery path and confirms the Label Print Service can recover from a Windows reboot without a user manually starting the desktop batch file.

## Verify SSH Server Locally

If direct access to `PRINT-SERVER` is available and SSH is not reachable, use an elevated PowerShell session to check:

```powershell
Get-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

```powershell
Get-Service sshd | Select-Object Name,Status,StartType
```

```powershell
Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" |
    Select-Object Name,Enabled,Direction,Action
```

```powershell
Get-NetTCPConnection -LocalPort 22 -State Listen |
    Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Accepted configuration:

```text
OpenSSH Server: Installed
sshd: Running
sshd StartType: Automatic
OpenSSH-Server-In-TCP: Enabled / Inbound / Allow
TCP 22: listening
```

If `sshd` is installed but stopped:

```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

Do not change firewall scope, authentication policy, Windows accounts, or SSH configuration files merely to troubleshoot connectivity without first determining the actual cause.

## Related Documents

- [Print Server Runtime Runbook](Print_Server_Runtime_Runbook.md)
- [Runtime Recovery — 2026-08-24](Label_Print_Service_Runtime_Recovery_2026-08-24.md)
- [Label Print Service Engineering Rules](../System_Documentation/Project_Rules/Label_Print_Service_Engineering_Rules.md)
- [Repository README](../readme.md)

## Revision History

| Date | Change |
|---|---|
| 2026-08-24 | Created from the verified PRINT-SERVER OpenSSH installation, pre-login reboot test, SSH login procedure, remote reboot command, reconnect procedure, and unattended Label Print Service recovery acceptance. |
