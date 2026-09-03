# Brother SNMP Status Evidence

| Document Control | Value |
|---|---|
| Document Type | Engineering Test Evidence |
| System | MSB Label Print Service / PRINT-SERVER |
| Printers | PT-P950NW and QL-820NWB |
| Status | CURRENT — recovered bench evidence plus active-job capture contract |
| Last Reviewed | 2026-09-03 |
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

### Active-job sampler candidate

V4 `4.1.0-rc3` adds an observation-only PT-P950NW status sampler to every
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
sampler does not interpret an unknown byte as low tape, stop submission, clear
requests, or alter batch state. Its only purpose in this candidate is to
capture the racing-stripe transition so a later change can be based on physical
evidence.

When a natural runout produces `event=CHANGED`, preserve the complete batch log
with the physical last-good/boundary-label observation in this repository and
Issue #19 before beginning another runout or recovery experiment.

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
6. During the controlled natural-runout test, capture the complete raw 32-byte status repeatedly before the stripes, throughout the striped section, and through full exhaustion.
7. Correlate every status transition with timestamp, batch/item identity, b-PAC return, and Windows spooler state so recovery never guesses whether the boundary label physically printed.
8. The operator dialog must demonstrably become visible and gain attention. A `PREFLIGHT_DIALOG_OPEN` log entry proves only that code attempted to create it.
9. Controlled acceptance must cover cassette replacement, Retry/Cancel, restart/resume, and no-double-print behavior before V4 deployment.
10. Active-job sampling is an evidence mechanism, not an approved automatic
    stop rule. No changed byte becomes a stop condition until a controlled
    physical runout proves its meaning and timing.

During later V4 acceptance, a pending 36 mm Container with 24 mm laminated tape returned the same proven 24 mm ready status value. Preflight correctly blocked printing. The operator initially reported no visible dialog and later found it buried behind six windows, confirming the unresolved focus/attention defect.
