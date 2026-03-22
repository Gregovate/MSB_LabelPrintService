# MSB Label Printing — Operator Guide

**Author:** Greg Liebig / Engineering Innovations, LLC  
**Date:** 2026-03-22  
**System Version:** Label Service v3.x  

This guide explains how to print display and container labels
using the Directus interface.

This is semi-production ready and any suggestions or problems
you may run into, please let Greg know so they can be corrected.

---

## ⚠️ IMPORTANT SAFETY NOTES

### Tape Must Be Installed

The system cannot reliably detect an empty tape cartridge.

Before printing:

✔ Verify tape cartridge is installed  
✔ Verify tape width matches template (1.4")  
✔ Verify printer is powered on and online  

---

## ▶ Starting the Label Print Service

The label printer will not print automatically unless the MSB Label Print Service is running on the office workstation. 

Normall it will be. But, if labels are not printing, this is the first thing to check. Next will be checking the tape cartridge to make sure this is stock to print on and it's not empty.

There will be a dedicated print sever setup in the near future. For now we must do this if it is not started.

### Start Procedure

1. Log into the office workstation.
2. Open **Command Prompt**.
3. Change to the root:

```powershell
cd C:\
start_label_service
```

Expected Startup Output

You should see a startup banner similar to this:

```
MSB Label Service — label_poll_service_v3.py
Version 3.0
Host    : MSB-Office-PC
PID     : #####
```
Then:

```
Startup health check PASSED.
Service READY — polling every 15 seconds.
Press Ctrl+C to stop.
```

If you do not see this message, the service is not ready.

⏹ Stopping the Label Print Service

To stop the service safely:

Click the red background command prompt window running the service

```
Press:
Ctrl + C
```

This stops polling cleanly.

✅ How to Confirm the Service Is Running

The service is running correctly if:

the PowerShell window remains open
no startup errors are shown
the log file is updating at:
C:\MSB_LabelService\logs\label_service.log

Typical healthy log messages include:

Poll tick - checking for pending labels.
No pending labels. Service idle.
⚠ If the Service Is Not Running

If labels are selected in Directus but nothing prints:

check whether the service PowerShell window is open
restart the service if needed
verify printer is powered on and has tape installed



## 🖥️ Accessing Label Printing

Use the Directus left navigation panel.

![Directus Menu](images/directus_menu.jpg)

### Display Labels


Display → Print Display Labels


### Container Labels


Container → Print Container Labels


---

## 📋 Printing Multiple Labels at Once

### Step 1 — Find the Items

Use the search box at the top of the table.

![Search](images/search_batch_edit.jpg)

Example:

- Type part of a container name
- Filter by location
- Narrow the list as needed

---

### Step 2 — Select Items

Use the checkbox column on the left side of the table.


![Container Selection](images/container_selection.jpg)


Select all items you want to print.

---

### Step 3 — Open Batch Editor

Click the pencil icon in the upper-right corner.

![Search](images/search_batch_edit_pencil.jpg)

This opens the batch editing panel.

---

### Step 4 — Enable Print Label

Toggle **Print Label → Enabled**


![Batch Edit Toggle](images/container_print_toggle.jpg)


Then save the changes.

---

## 🖨️ What Happens Next

After saving:

1. Labels are queued automatically
2. The print service creates a batch
3. Labels print at the label printer
4. The Print Label flag resets automatically after completion

No further action is required.

---

## ❗ If Printing Does Not Start

Check the following:

- Printer power
- Network connection
- Tape installed
- Correct tape width
- Printer not paused or offline

If problems persist, notify system administrator.

---

## ❗ If Tape Runs Out During Printing

Symptoms:

- Printer stops feeding tape
- Labels may be incomplete
- System may still mark batch complete

Action:

Note: This section is not tested as of 3/22/26-GAL

1. Load a new cartridge
2. Re-select labels that did not print
3. Enable **Print Label** again
4. Save to reprint

---

## 📦 Container Labels vs Display Labels

### Display Labels

- One label per display
- Typically printed in batches

### Container Labels

- Two labels printed per container
- Used for physical storage identification

---

## 📌 Best Practices

✔ Print labels in manageable batches  
✔ Verify output before removing items  
✔ Keep spare cartridges nearby  
✔ Do not power off printer during printing  

---

## 🆘 Support

Contact the MSB production database administrator
if printing repeatedly fails or produces incorrect labels.

---

## 🔄 Revision History

- Initial operator guide for Label Service v3