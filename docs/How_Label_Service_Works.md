# MSB Label Printing System — How It Works

**Author:** Greg Liebig / Engineering Innovations, LLC  
**Date:** 2026-03-22  
**System Version:** Label Service v3.x  

---

## 🎯 Purpose

This document explains the architecture and runtime behavior of the
MSB Label Printing System.

It is intended for administrators, developers, and future maintainers.

---

---

## 🎯 Purpose

The label system provides automated printing of:

- Display labels
- Container labels

directly from the MSB Production Database via Directus.

Operators request labels through the web interface.  
Printing is performed by a background service connected to the label printer.

---

## 🧩 System Components

### 1. Directus (User Interface)

Operators interact with Directus to:

- Search displays or containers
- Select items
- Enable **Print Label**
- Save changes

This sets a flag in the database.

No printing happens inside Directus itself.

---

### 2. PostgreSQL Database

The database stores:

#### Source Tables


ref.display
ref.container


Relevant field:


print_label BOOLEAN


When set to TRUE, the item is queued for printing.

---

#### Batch Tables

Printing is performed through snapshot batches:


ops.display_label_batch
ops.display_label_batch_item

ops.container_label_batch
ops.container_label_batch_item


These tables:

- Record what was printed
- Preserve historical audit data
- Prevent race conditions
- Allow recovery from failures

---

### 3. Label Polling Service


The service is started manually from the office workstation using:

```powershell
python label_poll_service_v3.py
```

Runs continuously on the office workstation.

Responsibilities:

- Poll database every 15 seconds
- Detect pending print requests
- Create batch records
- Generate CSV files
- Print labels via b-PAC
- Verify completion through Windows spooler
- Finalize batches
- Clear print flags

---

### 4. Brother P-touch P950NW Printer

Connected via network.

Printing is performed using:


Brother b-PAC SDK


Templates are stored as `.lbx` files.

---

## 🔄 End-to-End Workflow

### Step 1 — Operator Requests Labels

Operator:

1. Opens Directus
2. Navigates to Print Display Labels or Print Container Labels
3. Selects items
4. Enables **Print Label**
5. Saves changes

Database effect:


print_label = TRUE


---

### Step 2 — Service Detects Pending Items

Every polling cycle:


SELECT COUNT(*) WHERE print_label = TRUE


If any items exist, the service begins a batch cycle.

---

### Step 3 — Safety Checks

Before printing:

✔ Database connectivity  
✔ Printer media compatibility  
✔ No active PRINTING batch exists  
✔ Printer queue is empty  

If any check fails, printing is deferred.

---

### Step 4 — Batch Creation (Snapshot)

A new batch record is created.

All pending rows are copied into batch item tables.

This snapshot ensures:

- Stable print set
- No changes mid-print
- Audit history
- Ability to retry safely

Original rows remain unchanged until success.

---

### Step 5 — CSV Generation

Batch items are exported to CSV:


csv/display_labels.csv
csv/container_labels.csv


This provides:

- Debug visibility
- Backup record of print content
- Simplified data transfer to print engine

---

### Step 6 — Label Printing via b-PAC

The service:

1. Opens LBX template
2. Sets printer
3. Populates template objects
4. Queues each label
5. Ends print job

Important:

b-PAC is used only to submit the job.

It is not trusted to report real completion status.

---

### Step 7 — Spooler Verification

After submission, the service monitors the Windows print queue.

Success criteria:

✔ A new job appears in the queue  
✔ That job clears within timeout  

Failure criteria:

✖ Job never appears  
✖ Job remains stuck  
✖ Printer offline/paused  

This is the authoritative success signal.

---

### Step 8 — Batch Finalization

If printing succeeds:

- Batch status → COMPLETED
- History records written
- Original rows updated:


print_label = FALSE
printed_by = actor
printed_at = timestamp


If printing fails:

- Batch status → FAILED
- Original rows remain flagged
- Operator may retry

---

## 🧠 Why Snapshot Batching Is Used

Direct printing from source tables would risk:

- Partial prints
- Lost data
- Race conditions
- Inconsistent output
- No audit trail

Batching ensures deterministic behavior.

---

## ⚠️ Known Limitations

### Tape-Out Detection

The printer may accept jobs even without tape installed.

Software cannot reliably detect empty media.

Operators must verify tape before printing.

---

### Cutter Behavior

Final full cut may not always occur depending on
printer settings and flags.

This does not affect label correctness.

---

## 🛡️ Safety Features

The system prevents runaway printing by:

- Allowing only one PRINTING batch at a time
- Requiring empty queue before new batch
- Verifying spooler completion
- Leaving flags set on failure
- Avoiding automatic retries

---

## 📦 Container vs Display Printing

### Display Labels

- One label per display
- Printed as selected

### Container Labels

- Two labels per container
- Rows duplicated internally before printing

---

## 🔐 Actor Attribution

Two actors may be recorded:

- Service actor — who executed the batch
- Requester actor — who requested labels

(Current implementation may record service actor only.)

---

## 🧪 Debug Logging

Logs stored at:


logs/label_service.log
batches/*.log


Batch logs include:

- Snapshot info
- Print queue activity
- Errors
- Completion status

---

## 🧭 Recovery Procedures

If printing fails:

1. Correct printer issue
2. Re-enable **Print Label**
3. Save to retry

Old batches remain for audit.

---

## 🏁 Summary

The MSB Label Printing System is designed for:

✔ Reliability  
✔ Auditability  
✔ Operator simplicity  
✔ Failure safety  
✔ Minimal manual intervention  

It converts simple UI actions into controlled,
verifiable physical printing.

---

## 🔄 Revision History

- v3.0 — Queue-verified printing architecture