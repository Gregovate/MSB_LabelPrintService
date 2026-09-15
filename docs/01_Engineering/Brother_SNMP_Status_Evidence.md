# Brother SNMP Status Evidence

| Document Control | Value |
|---|---|
| Document Type | Engineering Test Evidence |
| System | MSB Label Print Service / PRINT-SERVER |
| Printers | PT-P950NW and QL-820NWB |
| Status | CURRENT — recovered bench evidence plus production natural-runout evidence |
| Last Reviewed | 2026-09-15 |
| Controlling Issue | [#19](https://github.com/Gregovate/MSB_LabelPrintService/issues/19) |

## Purpose

This record preserves the raw Brother SNMP packets supplied during controlled printer/media tests before V4 implementation. The original diagnostic output was written to a Git-ignored local results directory and was not committed at the time. These values were recovered from the original ChatGPT project conversations on 2026-09-02.

No missing bytes have been reconstructed or inferred. A state without a valid captured packet is explicitly marked untested.

Both printers were queried using Brother's enterprise status OID:

```text
1.3.6.1.4.1.2435.3.3.9.1.6.1.0
```

Every valid reply below was a 78-byte SNMP packet containing a 32-byte Brother status value.

## PT-P950NW

Target and reply: `192.168.5.12:161/UDP`

### Valid test matrix

| Physical condition | Width | Type | Error 1 | Error 2 | Result |
|---|---:|---:|---:|---:|---|
| 36 mm laminated, ready | `0x24` | `0x01` | `0x00` | `0x00` | Ready |
| 36 mm laminated cassette, fully exhausted | `0x24` | `0x01` | `0x02` | `0x00` | End of media |
| No cassette, cover closed | `0x00` | `0x00` | `0x00` | `0x00` | No media is represented by zero media fields |
| No cassette, cover open | `0x00` | `0x00` | `0x00` | `0x10` | Cover open |
| 24 mm laminated, ready | `0x18` | `0x01` | `0x00` | `0x00` | Ready |
| 24 mm cassette installed, cover open | `0x00` | `0x00` | `0x00` | `0x10` | Cover open suppresses cassette identity |
| 12 mm laminated, ready | `0x0C` | `0x01` | `0x00` | `0x00` | Ready |
| Physical 12 mm heat-shrink cartridge | `0x0C` | `0x03` | `0x00` | `0x00` | Printer reports type `0x03`, not expected `0x11` |
| Low-tape striped end marker | — | — | — | — | Not captured; code/byte transition unknown |
| 18 mm cassette | — | — | — | — | Not tested in the recovered conversation |

### 36 mm laminated, ready

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 00 24 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 00 24 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

Observed: 36 mm laminated white tape with black ribbon; no errors.

### 36 mm laminated cassette, fully exhausted

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 02 00 24 01 00 00 00 00 00 00 02 00 00 00 00 00 01 08 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 02 00 24 01 00 00 00 00 00 00 02 00 00 00 00 00 01 08 00 00 00 00 00 00
```

Observed: cassette identity remains present; Error Information 1 is `0x02` (end of media), and status type is `0x02` (error occurred). This is the known **fully exhausted cassette** signature. It is not evidence of the earlier low-tape warning produced when the printer reads the striped end-marker tape.

### Missing low-tape/end-marker warning

Near the end of a cassette, striped tape passes through the printer before the usable tape is fully exhausted. The printer can read those stripes, but the corresponding Brother status byte/code has not been identified in the existing captures.

The controlled natural-runout test must begin logging before the striped section reaches the sensor and continue through the final `0x02` end-of-media state. Each sample must retain the complete raw 32-byte value and be correlated with precise timestamp, batch/item identity, b-PAC result, and Windows spooler state. Raw changes must be preserved even when the current decoder gives them no name.

### 2026-09-08 production natural runout

Controller batch 34 supplied the first production natural-runout evidence on
24 mm laminated tape.

The sampler captured this ready packet before b-PAC submission at
`2026-09-08 12:53:00`:

```text
80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

It captured the normal active-phase transition to `phase=0x01`, but stopped at
`12:53:07`, two seconds after Windows spooler job 33 cleared. The final sampled
packet still reported `phase=0x01`:

```text
80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 00 00 00 01 00 00 00 00 01 08 00 00 00 00 00 00
```

Physical observation established the boundary:

- the old cassette printed `CTRL:1098`;
- a green end marker appeared immediately before the racing stripes;
- the tape exhausted at that point;
- after a new 24 mm cassette was installed, the Brother/driver printed
  `CTRL:1098` again without another V4 submission;
- the one boundary-label replay is acceptable;
- V4 must not independently submit the completed Controller a third time.

At `12:53:22`, the next normal poll found another pending Controller and
captured the fully exhausted cassette during preflight:

```text
80 20 42 30 70 30 04 00 02 00 18 01 00 00 00 00 00 00 02 01 00 00 00 00 01 08 00 00 00 00 00 00
```

This packet proves `error1=0x02`, `status=0x02`, and `phase=0x01` for the
exhausted 24 mm cassette. It does not prove a separate earlier low-tape byte.
The fixed two-second post-spooler window missed the physical tape-out because
sampling stopped while Brother still reported an active phase.

Database safety succeeded. The completed batch was not re-requested, the 13
later pending Controllers remained requested, and a controlled service restart
printed exactly those 13 without a database reset or a third `CTRL:1098`.

### 2026-09-15 production 36 mm runout — Container batch 348

Container batch 348 submitted two horizontal `C037` copies through one Windows
spooler job. The initial Brother packet reported ready 36 mm laminated tape:

```text
80 20 42 30 70 30 04 00 00 00 24 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

At `2026-09-15 10:40:53`, while spooler job 2 remained observed, the sampler
captured the natural tape-out transition:

```text
error1=0x02 status=0x02 phase=0x01 errors='End of media'
80 20 42 30 70 30 04 00 02 00 24 01 00 00 00 00 00 00 02 01 00 00 00 00 01 08 00 00 00 00 00 00
```

The sampler retained that state through 344 samples. Rc4 nevertheless allowed
the spooler-clear timeout to keep counting and marked batch 348 `FAILED` after
90 seconds with:

```text
Observed spooler job(s) did not clear within 90 seconds: [2]
```

Physical and runtime evidence then established a critical boundary:

- one pre-runout C037 label emerged but was unusable and discarded;
- V4 was stopped and the Windows queue reported no jobs;
- the exhausted cassette was removed and the cover remained open;
- installing a fresh 36 mm cassette caused the Brother/driver to resume the
  retained original job and print two complete C037 labels;
- no new V4 process or application-level submission caused those labels;
- the empty Windows queue therefore did **not** prove that Brother had discarded
  the submitted job;
- batch 348 was reconciled as `COMPLETED`, its one logical item was recorded as
  two successful physical Container labels, and `ref.container.print_label`
  was cleared without another application submission.

This event proves that fully exhausted media is a recoverable pause for the
already-submitted Brother job. It must suspend the spooler and physical wait
timeouts rather than convert the batch to `FAILED` while the printer is waiting
for replacement media.

### Active-job sampler behavior

V4 `4.1.0-rc3` added a PT-P950NW status sampler to every
Display, Container, and Controller b-PAC job. It starts before `StartPrint`,
continues while the Windows spooler job is active, and remains active for two
seconds after the observed job clears. The default interval is 250 ms with an
unchanged-status heartbeat every five seconds.

The batch log records:

- `BROTHER_STATUS_SAMPLE event=INITIAL` before b-PAC submission;
- `event=CHANGED` for every raw 32-byte transition;
- `event=HEARTBEAT` while the packet is unchanged;
- `event=RECOVERED` after a transient query error;
- `BROTHER_STATUS_SAMPLE_ERROR` for query failures;
- `BROTHER_STATUS_SAMPLER_STOP` with sample, change, and error totals plus the
  final raw value.

Every sample retains width, media type, both error bytes, status type, phase,
notification byte, decoded known errors, and the complete raw value. The
sampler does not interpret an unknown byte as low tape or stop submission.
Candidate rc5 does use already-proven media states—end of media, cover open, no
media, wrong width, and wrong type—to pause completion timeouts around the
retained job. Unknown transitions remain evidence-only.

The September 8 event proved that the original fixed post-spooler window was
not sufficient. Production `4.1.0-rc4` removed that timer. After the observed
Windows job clears, the sampler continues until Brother reports one of these
physical terminal conditions:

- ready/idle (`phase=0x00`) continuously for the configured stability window;
- fully exhausted cassette (`error1=0x02`);
- another explicit Brother error;
- bounded physical-completion timeout.

The first fresh sample after spooler clearing is required before ready/idle can
be accepted. A new preflight also rejects `phase != 0x00`, preventing the next
batch from starting while the Brother/driver is still physically completing or
replaying the prior label.

The September 15 event then proved that rc4 could fail before reaching that
post-spooler logic when the observed job remained queued for replacement media.
Candidate `4.1.0-rc5` pauses both the spooler-clear timeout and the later
physical-completion timeout for known recoverable media conditions. It waits
for the correct cassette, retained-job completion, and ready/idle before
finalizing the same database batch.

Unknown raw-byte transitions remain evidence-only. Rc5 does not invent a
low-tape code or submit an application-level copy of the boundary label.

### No cassette, cover closed

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

Observed: no error bit identifies this state. No cassette must be detected from width/type `0x00/0x00`.

### No cassette, cover open

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00
```

Observed: Error Information 2 is `0x10` (cover open), status type is `0x02`, and media identity is unavailable.

### 24 mm laminated, cover closed/ready

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

Observed: 24 mm laminated media, no errors.

### 24 mm cassette physically installed, cover open

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00
```

Observed: identical to no-cassette/cover-open. Cover-open must be evaluated before no-media or wrong-width because the printer suppresses cassette identity while the cover is open.

### 12 mm laminated, ready

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 00 0C 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 00 0C 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

Observed: 12 mm laminated media, no errors.

### Physical 12 mm heat-shrink cartridge, ready

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 30 70 30 04 00 00 00 0C 03 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00

Status value:
80 20 42 30 70 30 04 00 00 00 0C 03 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00
```

Observed: the physical heat-shrink cartridge reported width `0x0C` and media type `0x03`, which Brother's table labels non-laminated. It did not report the expected heat-shrink code `0x11`. Runtime validation must preserve and use the tested response for the actual stock.

## QL-820NWB

Target and reply: `192.168.5.11:161/UDP`

Available physical stock during testing: DK-2251 black/red on white, 62 mm continuous roll.

### Valid test matrix

| Physical condition | Width | Type | Error 1 | Error 2 | Result |
|---|---:|---:|---:|---:|---|
| DK-2251 installed, cover closed | `0x3E` | `0x0A` | `0x00` | `0x00` | Ready |
| No roll, cover closed | `0x00` | `0x00` | `0x00` | `0x00` | No media |
| DK-2251 installed, cover open | `0x00` | `0x00` | `0x00` | `0x10` | Cover open |

A natural QL end-of-roll and other DK media types were not available and remain untested.

### DK-2251 installed, cover closed/ready

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 34 41 30 04 00 00 00 3E 0A 00 00 23 00 00 00 00 00 00 00 00 00 00 81 00 00 00 00 00 00

Status value:
80 20 42 34 41 30 04 00 00 00 3E 0A 00 00 23 00 00 00 00 00 00 00 00 00 00 81 00 00 00 00 00 00
```

Observed: 62 mm continuous media, no errors.

### No roll, cover closed

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 34 41 30 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00

Status value:
80 20 42 34 41 30 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00
```

Observed: media width/type zero with the cover closed.

### DK-2251 installed, cover open

```text
SNMP packet:
30 4C 02 01 00 04 06 70 75 62 6C 69 63 A2 3F 02 01 01 02 01 00 02 01 00 30 34 30 32 06 0E 2B 06 01 04 01 93 03 03 03 09 01 06 01 00 04 20 80 20 42 34 41 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 01 00 00 00 00 00 00

Status value:
80 20 42 34 41 30 04 00 00 10 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 01 00 00 00 00 00 00
```

Observed: cover-open error and suppressed media identity.

## Invalid probe attempts

Two operator-labeled P950 tests (cover open and empty 36 mm cassette) accidentally targeted `192.168.5.11`. Their model bytes were `42 34 41`, and both returned the QL-820NWB ready packet. They are preserved in the conversation history but excluded from the P950 evidence matrix.

## V4 requirements established by the evidence

1. Evaluate cover-open before interpreting media identity.
2. Detect no cassette/roll from zero media fields; do not depend only on error bits.
3. Detect the fully exhausted P950 cassette from Error Information 1 `0x02` while retaining cassette width/type.
4. Do not conflate `0x02` with the still-unidentified low-tape striped end-marker warning.
5. Validate required width and tested media type before creating a database execution batch.
6. During natural runout, capture the complete raw 32-byte status repeatedly before the stripes, throughout the striped section, and through full exhaustion.
7. Correlate every status transition with timestamp, batch/item identity, b-PAC return, and Windows spooler state so recovery never guesses whether the boundary label physically printed.
8. The non-blocking operator notice must demonstrably appear in the active PRINT-SERVER console and identify required/detected media. A log-only event is not operator notice.
9. Controlled acceptance must cover cassette replacement, automatic recovery, wrong replacement media, notice delivery, restart/resume, and no-double-print behavior.
10. Active-job sampling is an evidence mechanism, not an approved automatic
    stop rule. No changed byte becomes a stop condition until a controlled
    physical runout proves its meaning and timing.
11. A known `error1=0x02` active-job tape-out is a recoverable wait state, not
    proof of batch failure. Completion timeouts must pause while Brother retains
    the submitted job, and an empty Windows queue must not trigger a duplicate
    application submission.

During later V4 acceptance, a pending 36 mm Container with 24 mm laminated tape returned the same proven 24 mm ready status value. Preflight correctly blocked printing. The operator initially reported no visible dialog and later found it buried behind six windows, confirming that worker-owned desktop dialogs were not an acceptable notification path.

During the September 8 production runout, the worker logged
`PREFLIGHT_DIALOG_OPEN` from Session 0 but no message appeared on the
PRINT-SERVER console. The worker then blocked indefinitely until it was
manually restarted. Production `4.1.0-rc4` removes that blocking call and uses a
non-blocking Windows Terminal Services notice plus automatic preflight recheck.
The September 15 evidence separately proved that rc4 did not recover an active
job whose spooler timeout expired during tape-out. Candidate rc5 adds that
same-batch retained-job recovery; it does not claim to identify the earlier
racing-stripe warning.
