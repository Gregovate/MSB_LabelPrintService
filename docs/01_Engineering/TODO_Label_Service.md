# MSB Label Service — Follow-Up TODO / Enhancements

**Author:** Greg Liebig / Engineering Innovations, LLC  
**Date:** 2026-03-22  
**System Version:** Label Service v3.x  

This document tracks known limitations, debugging items, and future improvements
for the MSB Label Polling Service (v3.x).
Updated: 26-03-22

---

## 🟥 Critical — Reliability / Safety

### ❗ Tape-Out Detection Is Not Reliable

Current behavior:

- Printer may accept jobs even with empty cartridge
- b-PAC reports success
- Windows spooler may clear job normally
- No definitive software signal that media actually printed

**Interim operator requirement:**

Operators must visually verify tape status before starting large print jobs.

**Future work:**

Investigate alternative detection methods:

- Printer SNMP status (if supported)
- USB status channel
- Brother network status API (if any)
- Job byte count vs media consumption
- Hardware sensor or operator confirmation workflow

---

## 🟧 Important — Cutter Behavior

### ❗ Full Cut Not Occurring at End of Batch

Current behavior:

- Labels print correctly
- Half cuts occur between labels
- Final full cut is inconsistent or absent

---

### 🔬 Planned Test Script

Create a minimal standalone test:

- One template
- Three labels
- No database involvement

Test these flag combinations:

#### Test A — Current Production Flags

```
0x200 | 0x400 | 0x04000000
```

- Half cut
- Chain print
- Cut at end

#### Test B — No Chain Print

```
0x200 | 0x04000000
```

#### Test C — Cut At End Only

```
0x04000000
```

#### Test D — Half Cut Only

```
0x200 | 0x400
```

---

### 🔍 Investigate Additional Factors

- Template settings inside LBX
- Driver cutter configuration
- Firmware behavior for P950NW
- Effect of `EndPrint` call timing
- Need for explicit form feed / advance
- Interaction with chain printing mode

---

## 🟨 Medium — Actor Attribution

### ❗ Requester vs Service Actor

Currently:

- Batches are attributed to PrintService account
- Original requester is not recorded

Future improvements:

- Capture `requested_by_person_id`
- Support multiple requesters
- Prevent mixed-actor batches
- Add audit trail of who initiated printing

---

## 🟩 Nice to Have — Operational Improvements

### Queue Safety

Already implemented:

- Active PRINTING batch guard
- Queue must be empty before new batch
- Spooler verification required for success

Potential enhancements:

- Detect stuck jobs automatically
- Provide operator recovery instructions
- Auto-cancel stale jobs after timeout

---

## 📌 Current Production Status

**Display Labels:** Operational  
**Container Labels:** Not yet validated  
**Tape-Out Detection:** Not reliable  
**End-of-Batch Cut:** Needs refinement  

---

## 🔄 Revision History

- v3.0 — Queue-verified printing operational