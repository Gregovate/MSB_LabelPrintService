# MSB Label Print Service v4 — Architecture and Acceptance Contract

| Document Control | Value |
|---|---|
| Status | IN DEVELOPMENT — accepted engineering contract; implementation/acceptance incomplete |
| System | MSB Label Print Service / PRINT-SERVER |
| Branch | `agent/runtime-preflight-hardening` |
| Primary Issue | LabelPrintService #14 |
| Last Updated | 2026-09-02 |
| Production Baseline | `label_poll_service_v3.py` v3.4 remains rollback path until v4 is proven |

## Purpose

This document is the durable engineering record for the Label Print Service v4 work. It captures accepted architecture, database contracts, physical template contracts, printer/media behavior, preflight rules, operator interaction, logging requirements, tape-out evidence requirements, and controlled acceptance criteria.

The design decisions in this document are authoritative for the v4 workstream unless superseded by a later repository change. Chat history and GitHub issue comments are supporting evidence only and must not be the sole source of system behavior.

## Ownership Boundary

Repository location does not change subsystem ownership.

### Production Database owns

- authoritative Display, Container, Location, and Controller business records;
- governed logical label-family assignments;
- print request flags and print/batch history;
- `ref.label_template` logical/physical family catalog;
- database FKs and batch-state persistence.

The Production Database must not store PRINT-SERVER-local Windows queue names or absolute `.lbx` paths as business-record configuration.

### LabelPrintService owns

- Brother b-PAC rendering;
- `.lbx` physical templates;
- local template directories;
- Windows printer queue mapping;
- Brother printer host/IP mapping;
- SNMP status decoding;
- printer/media/template preflight;
- Windows spooler observation;
- per-label execution logging;
- operator dialogs shown on PRINT-SERVER;
- no-double-print safeguards;
- printer-specific runtime behavior.

### FieldWiring owns label requests, not printer integration

FieldWiring may request plug/output labels from approved wiring data. It must not create a second Brother printer stack if LabelPrintService can render the requested label class.

## Production / Development Separation

Until v4 acceptance is complete:

- `label_poll_service_v3.py` v3.4 is the known rollback implementation;
- `config.local.ini` remains the v3 production configuration;
- `label_poll_service_v4.py` is development only;
- `config.v4.local.ini` is local-only and Git-ignored;
- the Scheduled Task remains stopped during controlled development/testing unless explicitly started for acceptance;
- obsolete root-level/legacy `.lbx` files remain in place until v4 is proven.

The v4 implementation must not require destructive removal of the v3 rollback path before acceptance.

## Physical Template Organization

Physical templates are organized by printer family:

```text
templates/
    pt_p950nw/
    ql_820nwb/
```

### Accepted PT-P950NW laminated template family

```text
QR_label_1_line_horz_24mm.lbx
QR_label_2_line_horz_24mm.lbx
QR_label_1_line_horz_36mm.lbx
QR_label_2_line_horz_36mm.lbx
QR_label_1_line_vert_36mm.lbx
wiring_label_2_line_horz_12mm_double_sided.lbx
```

The surviving Wiring LBX is one physical fold-over template. It prints the same `objChannel`, `objLine1`, and `objLine2` values on both halves of the label. The two obsolete single-sided Wiring templates were removed and must not remain in V4 configuration.

Do not create unused template variants merely for symmetry. There is no accepted 24 mm vertical template and no accepted two-line 36 mm vertical template at this time.

## Logical Label Families

The database identifies physical/logical label families; LabelPrintService maps those families to actual local `.lbx` files.

The accepted catalog is:

| ID | Code | Width | Orientation | Class | Current use |
|---:|---|---:|---|---|---|
| 1 | `QR_36MM_HORIZONTAL` | 36 mm | HORIZONTAL | `QR_IDENTITY` | Existing Displays; horizontal Containers |
| 2 | `QR_24MM_HORIZONTAL` | 24 mm | HORIZONTAL | `QR_IDENTITY` | Selected Displays; permanent Controller ID labels |
| 3 | `QR_36MM_VERTICAL` | 36 mm | VERTICAL | `QR_IDENTITY` | Vertical Containers |
| 4 | `WIRING_12MM_HORIZONTAL` | 12 mm | HORIZONTAL | `WIRING` | FieldWiring controller-output labels |

### Current live assignments at 2026-08-31

- all 1,056 existing `ref.display` rows are assigned `label_template_id = 1`;
- no known Display has yet been intentionally changed to the 24 mm family;
- all 177 current `ref.controller` rows have `label_template_id IS NULL` pending explicit assignment;
- Containers do not currently FK to `ref.label_template`; existing Container orientation logic remains authoritative for horizontal vs vertical selection.

## `ref.label_template` Database Contract

The old asset-specific rows (`DISPLAY_*`, `CONTAINER_*`) were corrected in production on 2026-08-31 to represent the four generic families above.

`template_relative_path` was made nullable because the database must not be required to know local `.lbx` filenames. LabelPrintService owns the local family-to-template mapping.

The production schema change must also be captured in the Production Database repository before the workstream is considered fully reconciled.

## Display Batch Family Contract

`ops.display_label_batch` now contains nullable `label_template_id` with FK:

```text
ops.display_label_batch.label_template_id
    -> ref.label_template(label_template_id)
```

Historical batches may remain NULL. New v4 Display batches must populate this FK.

One Display execution batch must contain exactly one compatible label family. In particular:

- 24 mm and 36 mm Displays must never enter the same batch;
- unprinted incompatible pending Displays must remain requested;
- a completed batch must not clear flags for rows outside its own snapshot;
- mixed pending families must be handled deterministically rather than guessed.

The batch-item table already freezes `qr_url`, `line1`, and `line2`. A separate per-item physical-template filename is not required.

## Container Contract

Containers are always printed on 36 mm laminated tape, but both orientations are required.

```text
HORIZONTAL Container
    -> QR_36MM_HORIZONTAL
    -> QR_label_1_line_horz_36mm.lbx

VERTICAL Container
    -> QR_36MM_VERTICAL
    -> QR_label_1_line_vert_36mm.lbx
```

The existing database-driven `label_orientation` rule remains. v4 replaces the old Container-specific LBX filenames with the generic physical templates; it does not collapse all Containers to one orientation.

The generic Container QR template object contract is:

```text
objLine1 = existing human-readable Container label, such as C216
objQr    = Container QR payload
```

The old Container-specific `objContainerLabel` object is a v3 template dependency and is not part of the accepted v4 generic template contract.

Current Container quantity behavior remains two physical labels per selected Container unless separately changed and accepted.

For v4, newly printed/replacement Container labels retain the exact V3 full URL: `https://db.sheboyganlights.org/scan/CONT/<container_id>`. This is implemented in `sql/container_snapshot_v4.sql`. Zebra ADF may shorten that URL to `CONT:<container_id>` plus carriage return during HID transmission; the physical QR remains phone-compatible.

During the current polling transition, if both Display and Container requests are pending, v4 processes the selected Display workload first and leaves Container requests untouched for a later poll. This is a deterministic safety rule that avoids mixing 24 mm Display work with 36 mm Container work in one execution cycle.

## Display / Controller QR Rendering Contract

Display identity labels use their assigned horizontal 24 mm or 36 mm physical family. Permanent Controller ID labels use the 24 mm one-line QR template after the Controller scan route and V4 Controller polling path are implemented and accepted.

Within a family, LabelPrintService chooses the one-line or two-line physical template based on the actual human-readable text.

The database/user does not choose one-line vs two-line.

Conceptually:

```text
assigned QR_36MM_HORIZONTAL
    -> inspect text
    -> short enough: QR_label_1_line_horz_36mm.lbx
    -> longer: choose safe split and use QR_label_2_line_horz_36mm.lbx
```

The same applies to the 24 mm horizontal family.

For the current Display label population, the accepted v4 compatibility rule preserves the established production split behavior:

```text
display_name length <= 20
    -> one-line template

display_name length > 20
AND the name contains at least two leading hyphen-delimited segments
    -> split after the second segment
    -> two-line template

display_name length > 20
AND that two-hyphen structure is absent
    -> keep the complete name on the one-line template
```

The 2026-08-31 profile found 107 Display names over 20 characters. 103 follow the established two-hyphen split structure. Three confirmed valid long names intentionally remain one-line:

```text
CL-LollipopTrailerNetLights
MI-ProgramTrailerPallets
PB-SlidingPenguinsString
```

`display_id 650` (`SecurityLight-FoodTruck`) was identified during this review as incorrect upstream/master data that does not follow the naming standard and does not represent a real Food Truck Display. It must be corrected upstream and re-parsed; v4 must not add a renderer special case for that bad row.

The purpose of the one-line/two-line selection is to avoid printing hundreds of otherwise compact labels as wasteful single-line tape while preserving exact Display identity text.

### Safe split behavior

- preserve the exact Display name content;
- use the established second-hyphen split where the naming structure supports it;
- allow the confirmed valid long exceptions above to remain one-line;
- snapshot the final `line1`/`line2` values used for the batch;
- once the batch is created, the frozen render intent must not be silently recomputed from later source edits.

## Template Object Contracts

### QR one-line templates

```text
objQr
objLine1
```

One-line templates intentionally use a larger font and do not contain `objLine2`.

### QR two-line templates

```text
objQr
objLine1
objLine2
```

### Wiring fold-over template

```text
objChannel  (two visual copies)
objLine1    (two visual copies)
objLine2    (two visual copies)
```

The two halves are not separate records and do not receive different values. One Wiring record supplies one `objChannel`, one `objLine1`, and one `objLine2`; those same three values appear on both halves so the label remains readable after it is folded around the wire.

The corrected LBX contains duplicate visual objects with the same three b-PAC names. CSV/database merge has been physically demonstrated to populate both halves. Direct b-PAC assignment through `GetObject(name).Text` was tested on 2026-09-02 with the export-only probe.

The proof **failed**: the left half changed to `09 / FOLDOVER-PROBE-A / FOLDOVER-PROBE-B`, while the right half retained `11 / Santa's Station Sign / Twist 01`. One `GetObject(name)` assignment reaches only the first matching visual object.

The physical fold-over design and one-record/same-three-values contract remain correct, but the current duplicate-name LBX is not safe for V4 direct assignment. Before runtime activation, either give the second-side objects unique b-PAC names and assign the same three values to both name sets, or prove a supported enumeration method that updates every matching object. Then rerun the export-only probe and require both halves to match.

The probe is `tests/printer_diagnostics/export_wiring_foldover_probe.py`. It does not select a printer or call `SetPrinter`, `StartPrint`, or `PrintOut`. The failed bitmap is `tests/printer_diagnostics/evidence/wiring_foldover_direct_assignment_20260902_162008.bmp` and must be committed as acceptance evidence.

For Wiring, `objChannel` is the physical controller output/channel and is visually dominant. `objLine1` and `objLine2` are the two installer-facing descriptive lines. The service must never split or rewrite `objChannel`; it must send the three governed values supplied by the Wiring request/snapshot contract.

Example render intent:

```text
objChannel = 09
objLine1   = Caroler
objLine2   = Mouth Open 2
```

Each value above is repeated unchanged on the second half of the fold-over label.

## Wiring Label Purpose

The 12 mm Wiring label is intentionally smaller than the permanent identity labels. The smaller label is a field hookup/configuration label, not a permanent asset identity label.

The visual goal is to improve field readability beyond handheld-printer labels by showing the physical controller output/channel number prominently while retaining only useful descriptive connection metadata for confirmation.

The channel number alone does not identify a particular controller. Specific controller identity, Stage, network, UID/address, universe, and other context remain available through the wiring system rather than being permanently encoded into every descriptive wiring line.

FieldWiring already exposes structured `physical_output`, `display_name`, and `channel_name` data in its read-only wiring package. It does not yet provide the lead/display label-selection and request workflow. That request contract, snapshot/finalization path, and no-double-print behavior remain in the FieldWiring workstream; the shared LabelPrintService remains the only Brother printing stack.

## QR Payload Compatibility

The accepted physical QR payload for both permanent Display and Container identity labels is the exact V3 full scan URL:

```text
Display:   https://db.sheboyganlights.org/scan/DISP/<display_id>
Container: https://db.sheboyganlights.org/scan/CONT/<container_id>
```

Existing and newly printed labels therefore remain directly usable by phone cameras. Zebra Advanced Data Formatting owns scanner-side shortening for Bluetooth HID entry:

```text
https://db.sheboyganlights.org/scan/DISP/<id> -> DISP:<id> + carriage return
https://db.sheboyganlights.org/scan/CONT/<id> -> CONT:<id> + carriage return
```

Do not restore the superseded compact physical Container payload. The V4 snapshot SQL must freeze the full URL in the existing `qr_url` field.

Location/rack Code 128 labels use `LOC:<location_code>` because that is the accepted compact machine identity for that separate label class.

Permanent Controller labels are intended to use a full phone-compatible Controller scan URL in `objQr` and visible `CTRL:<controller_id>` text. No accepted `/scan/CTRL/<controller_id>` route exists yet, so permanent Controller labels must not be printed with an assumed dead URL. The Production Database workstream must implement and accept the exact route first.

## Printer Runtime Mapping

v4 configuration is printer-specific and family-specific.

### PT-P950NW

- Windows queue: `Brother PT-P950NW`
- host/IP: `192.168.5.12`
- template directory: `C:\MSB_LabelService\templates\pt_p950nw`
- used for 12/24/36 mm laminated tape families.

### QL-820NWB

- Windows queue: `Brother QL-820NWB`
- host/IP: `192.168.5.11`
- template directory: `C:\MSB_LabelService\templates\ql_820nwb`
- Location/rack Code 128 printing is a required V4 deliverable; the governed request/batch/poller/finalizer and physical acceptance remain incomplete.

The QL mapping must remain easy to enable later without redesigning the PT-P950NW code path.

## Windows Spooler Boundary

The Beelink does not need to act as a traditional shared Windows print server for other machines. However, the current b-PAC architecture still requires:

- locally installed Brother Windows printer queues;
- Brother drivers;
- Windows Print Spooler;
- `SetPrinter()` against the local queue;
- spooler observation through `win32print`.

Windows queue completion is not proof that the physical label printed correctly. It is only evidence that Windows finished processing the job.

The evidence sources are intentionally separate:

```text
SNMP
    -> printer reachability / media / cover / end-of-media state

Windows spooler
    -> submitted Windows job appearance / state / clearing

b-PAC
    -> LBX rendering and submission
```

## Full Preflight Rule

The controlling v4 safety rule is:

> If full preflight does not pass, PostgreSQL execution-batch state must remain unchanged.

For a failed preflight there must be:

```text
NO new batch header
NO new batch items
NO print_label clearing
NO print-history success mutation
NO DBA cleanup requirement
```

Full preflight runs once for a selected compatible pending workload immediately before batch creation. It is not repeated before every physical label.

At minimum, full preflight must verify:

- required SQL/runtime files exist and are readable;
- required runtime directories exist or can be safely created;
- output/CSV paths are writable without destructive overwrite;
- selected label-family runtime mapping exists;
- correct Windows printer queue is installed/selectable;
- printer is reachable;
- Brother SNMP status returns successfully;
- loaded media is present and matches required width/type;
- cover/media errors are rejected;
- selected template exists;
- b-PAC can open the selected template;
- required template objects exist for the selected one-line/two-line contract;
- Windows queue is safe/empty before starting;
- no conflicting active/failed batch blocks safe execution;
- logs/state paths are usable.

Defensive directory creation immediately before write is still allowed as race protection, but it is not a replacement for preflight.

## Known Brother PT-P950NW Status Evidence

The Brother status probe uses OID:

```text
1.3.6.1.4.1.2435.3.3.9.1.6.1.0
```

Controlled observations already captured include:

- 36 mm laminated ready: width `0x24`, type `0x01`;
- 24 mm laminated ready: width `0x18`, type `0x01`;
- 12 mm laminated ready: width `0x0C`, type `0x01`;
- exhausted 36 mm cassette: width `0x24`, type `0x01`, Error Information 1 includes `0x02`;
- no cassette / cover closed: width `0x00`, type `0x00`;
- cover open: Error Information 2 includes `0x10`; media identity is not reported.

Brother documentation identifies Error Information 1 bit `0x02` as End of media. The recovered packet proves the fully exhausted cassette state, not the earlier low-tape warning. The striped end-marker transition remains unidentified and must be captured during a controlled natural runout. The complete raw PT-P950NW and QL-820NWB packets, including invalid and untested cases, are preserved in [Brother SNMP Status Evidence](Brother_SNMP_Status_Evidence.md).

No SNMP response/timeout/network error is treated as printer unavailable. There is no need to invent a powered-off status byte.

## QL-820NWB Status Evidence and Gate

The same Brother SNMP OID responds on the QL-820NWB. Raw packets are preserved in [Brother SNMP Status Evidence](Brother_SNMP_Status_Evidence.md).

Evidence collected with DK-2251 includes repeatable READY, no-media, and cover-open responses. Only one QL media type was available, so comparative media identity and a natural QL end-of-roll remain untested.

Location/rack production printing is a required V4 deliverable. The accepted LBX uses:

```text
objCode128 <- LOC:<location_code>
objLine1   <- location_code
```

The remaining work is the governed database request and immutable batch/history contract, V4 polling/rendering/finalization, enabling the QL runtime configuration, controlled physical acceptance, and safe recovery behavior. The absence of a natural QL end-of-roll cartridge must be recorded as an explicit evidence gap rather than silently treated as passed.

## Operator-Correctable Preflight Dialogs

Recoverable preflight failures must not be log-only failures. v4 must display a visible blocking dialog on the PRINT-SERVER Beelink for operator-correctable conditions.

Example:

```text
MSB Label Service

Wrong tape cassette loaded.

Required: 24 mm laminated tape
Detected: 36 mm laminated tape

Change the cassette and close the cover,
then press Retry to continue.

[ Retry ]   [ Cancel ]
```

Expected behavior:

- `Retry` reruns full preflight; it does not create a batch first;
- `Cancel` returns the service safely to idle and leaves source `print_label` requests untouched;
- do not open a new popup every poll cycle while one recovery dialog already owns the condition;
- every displayed condition and operator response must also be logged.

Correctable dialog classes include at minimum wrong media width/type, no media, cover open, unavailable printer when retry is reasonable, and unsafe queue/intervention states.

The production Scheduled Task must run in the logged-on interactive Windows session so dialogs are visible. PRINT-SERVER autologin is enabled, but task configuration must still be verified during acceptance.

## Tape-Out During Active Printing

The fully exhausted cassette state is not a preflight condition when tape remains at batch start; it is a during-batch recovery condition. The earlier low-tape/end-marker warning may occur while printing and its Brother byte/code is not yet known.

The service must instrument the print loop before the next natural runout so it captures the raw transition as the striped tape passes the sensor and continues through the final `error1=0x02` exhausted state. No automatic recovery behavior may be assumed from the final code alone.

### Required per-label evidence

Immediately around each physical `PrintOut()` attempt, log enough context to identify the physical boundary label:

- batch ID;
- sequence number / total;
- asset class and ID;
- human-readable label text;
- selected label family;
- selected one-line/two-line template;
- expected media;
- Brother status immediately before submission and repeatedly during the controlled end-of-cassette diagnostic window;
- the complete raw 32-byte status value for every change, including currently unknown notification/status bytes;
- precise timestamps that correlate raw status, b-PAC submission, and spooler observations;
- `PrintOut()` result;
- Container copy number where one source row prints more than one physical label.

For Wiring also log `objChannel`, `objLine1`, and `objLine2`.

### Tape-out dialog

When the fully exhausted `error1=0x02` state is detected during an active batch, v4 must stop blindly advancing and show a visible dialog such as:

```text
Tape cassette is empty.

Replace with 36 mm laminated tape.
Close the cover.

[ Resume ]   [ Cancel ]
```

`Resume` must recheck reachability, cassette width/type, cover state, and readiness before continuing.

`Cancel` must stop safely and preserve evidence for controlled recovery.

### Boundary-label uncertainty

Do not implement application-level automatic reprint of the boundary label until controlled evidence proves whether Brother/b-PAC/Windows already resumes or reprints that interrupted label after cassette replacement.

When the next natural tape-out occurs, operators should report which label was physically printing/last visible. Correlate that report with the per-label and batch logs to determine actual driver/printer behavior.

Until proven otherwise, the boundary label at tape-out is considered uncertain.

## Main v4 Execution Order

The intended Display path is:

```text
poll pending requests
    -> resolve each Display label_template_id / label family
    -> select one homogeneous compatible family
    -> derive one-line/two-line render plan
    -> select printer/template/media mapping
    -> full preflight
    -> operator Retry/Cancel loop for correctable preflight failures
    -> only after PASS create display batch with label_template_id
    -> snapshot exactly the selected family and frozen line1/line2/QR content
    -> commit batch execution state
    -> print with per-label instrumentation
    -> observe Brother + spooler behavior
    -> finalize only confirmed successful snapshot rows
```

Container processing must preserve horizontal/vertical grouping and two-label quantity behavior while using the generic 36 mm templates.

## Mixed Pending Display Families

The current boolean request workflow allows a 24 mm and a 36 mm Display to be flagged at the same time.

Required safety behavior:

- never put incompatible media families into one execution batch;
- never clear flags for rows that were not physically included in the completed batch;
- leave incompatible pending work safely requested for later processing/cassette change;
- the operator must receive clear information when a cassette change is required.

The exact family-selection order may be deterministic, but it must not silently select the wrong cassette family.

## Current Boolean Workflow Remains for Setup

For the Setup-critical v4 pass:

```text
Directus
    -> ref.display.print_label = true
       / ref.container.print_label = true
    -> LabelPrintService polling
    -> family resolution
    -> full preflight
    -> execution batch
    -> print/finalize
```

Do not require the future Label Printing application or a new competing request table before Setup.

The design must leave reusable seams for a future Label Printing UI without replacing the current operational request authority prematurely.

## Controlled Acceptance Requirements

Before v4 replaces v3.4, prove at minimum:

### Configuration / rollback

- v3 files/config remain intact as rollback;
- v4 reads only `config.v4.local.ini` during development;
- secret v4 local config is Git-ignored;
- Scheduled Task remains controlled and is updated only after acceptance.

### Display 36 mm

- existing Display assignment resolves through `QR_36MM_HORIZONTAL`;
- one-line and two-line physical templates select correctly according to accepted threshold/safe split;
- correct printer/media/template objects are preflighted;
- successful print finalizes exactly the snapshot rows.

### Display 24 mm

- intentionally assigned Display resolves through `QR_24MM_HORIZONTAL`;
- wrong 36/12 mm media is rejected before batch creation;
- visible Retry/Cancel dialog appears;
- after cassette correction, Retry passes and exactly one controlled batch prints.

### Mixed Display families

- deliberately flag at least one 24 mm and one 36 mm Display simultaneously;
- prove they cannot enter the same batch;
- prove unprinted family remains requested;
- prove unrelated flags are not cleared;
- prove no manual PostgreSQL cleanup is needed merely because families were mixed.

### Container regression

- horizontal Container uses `QR_label_1_line_horz_36mm.lbx`;
- vertical Container uses `QR_label_1_line_vert_36mm.lbx`;
- quantity remains two physical labels per selected Container;
- current no-double-print protections remain intact.

### Fail-fast / no-DB-mutation preflight

Deliberately test missing runtime/output path, missing/unopenable template, wrong media, unavailable printer where safe, unsafe/non-empty queue, and missing required SQL/runtime file.

Every failed preflight must prove:

```text
NO batch header
NO batch items
NO print_label clearing
NO success history mutation
NO manual DB cleanup
```

### Operator dialogs

- wrong media dialog is visible on Beelink;
- Retry reruns preflight;
- Cancel leaves requests untouched;
- no repeated popup storm occurs;
- dialog action is logged;
- Scheduled Task interactive-session behavior is proven.

### Tape-out instrumentation

Before production rollout, per-label and short-interval diagnostic logging must be present so the striped low-tape transition and final exhaustion can be correlated with the physical label reported by staff. The raw 32-byte status must be retained even when a changed byte is not decoded yet.

Application-level boundary-label reprint remains unapproved until real evidence is obtained.

### Full-URL QR payload

Acceptance must prove at minimum:

- a newly printed/replacement Display QR encodes exactly `https://db.sheboyganlights.org/scan/DISP/<display_id>`;
- a newly printed/replacement Container QR encodes exactly `https://db.sheboyganlights.org/scan/CONT/<container_id>`;
- phone-camera scanning opens the correct scan route;
- Zebra ADF shortens the full URLs to `DISP:<id>` / `CONT:<id>` plus carriage return during HID transmission;
- already-deployed full-URL labels continue to resolve;
- V3.4 rollback retains its original full-URL behavior.

## v4 Full Preflight and Operator Retry/Cancel Gate

The v4 branch implementation uses Brother SNMP status as the physical
printer/media authority for PT-P950NW preflight. The decoder uses the same
documented 32-byte Brother status structure and field offsets already proven
by the repository diagnostic tools.

For the selected compatible Display or Container workload, the pre-batch gate
checks:

```text
required runtime directories exist and are writable
required SQL files exist and are UTF-8 readable
target CSV/output paths are writable
configured printer is enabled
Brother SNMP status responds
required tape width is loaded
required tape type is laminated tape
cover is closed / media is present / end-of-media is not active
every required LBX exists and opens in b-PAC
every required LBX contains the expected named objects
Windows printer queue can be inspected
Windows printer queue is empty/safe
```

Active/FAILED PostgreSQL batch guards remain before this gate.

If any gate fails, v4 shows one blocking Windows **Retry / Cancel** dialog in
the interactive PRINT-SERVER session. Retry reruns the entire gate. No
execution batch header/item or source `print_label` mutation is allowed before
the gate passes.

Cancel leaves pending source requests untouched and creates no execution
batch. To prevent a 15-second popup storm, v4 suppresses another dialog for the
exact same pending request set until that set changes or the service restarts.
The suppression is in-memory runtime state only and does not mutate
PostgreSQL.

After a Retry path finally passes full preflight, v4 re-reads a workload
signature before batch creation. Display signatures include `display_id`,
`display_name`, and `label_template_id`; Container signatures include
`container_id` and `container_type_id`. If that signature changed while the
operator dialog/preflight loop was active, v4 creates no batch and returns to a
fresh poll so the new workload is rebuilt and preflighted before any snapshot
state is written.

Immediately before the batch header is inserted, v4 freezes the exact pending
asset IDs, acquires row locks on those selected source rows, and rechecks the
validated workload signature again. The v4 snapshot SQL is restricted to those
exact IDs. The frozen rows also supply batch requester attribution. This closes
the final race between preflight and snapshot creation: a newly requested asset
cannot be swept into a batch that was not preflighted, and a selected row cannot
change its render-affecting source fields after the freeze until the snapshot
transaction completes.

The physical preflight plan itself is also atomic with its initial workload
signature. For Displays, one PostgreSQL statement returns the selected family,
one-line count, two-line count, and signature. For Containers, one statement
returns horizontal count, vertical count, and signature. This prevents a request
arriving between template-plan discovery and signature capture from introducing
an unpreflighted physical template into the later exact-ID snapshot.

Controlled acceptance must deliberately prove wrong 24/36 mm media, no
cassette, cover open, unavailable printer, unsafe queue, missing runtime
file/path, Retry recovery, Cancel suppression, and zero PostgreSQL execution
state change on every failed preflight.

## Remaining Required Work and Separate Workstreams

Required before V4 deployment:

- production Controller permanent-ID request-to-print support after the exact Controller scan route exists;
- production Location/rack Code 128 request-to-print support on the QL-820NWB;
- visible foreground operator alerts;
- active-print striped low-tape transition plus final-exhaustion/spooler/boundary-label instrumentation and controlled recovery;
- restart/resume and no-double-print acceptance;
- final Display and Container regression acceptance;
- installation as the interactive PRINT-SERVER autologin/autostart task while preserving V3.4 rollback.

Tracked separately but not implemented by inventing a second printer stack here:

- FieldWiring lead/display label selection/request UI and its governed snapshot/finalization contract;
- future general Label Printing application;
- unrelated cleanup of duplicate historical database constraints.

A natural QL end-of-roll remains an explicit hardware-evidence gap because only one non-empty DK-2251 roll was available. It must not be represented as a passed test.

## Repository Reconciliation Requirements

Before v4 is considered complete:

- all manually applied Production Database schema changes from this work must exist as controlled repo SQL/migration/documentation in `MSB-Production-Database-Project`;
- `config.v4.example.ini`, v4 code, template mappings, and operational docs must agree;
- obsolete asset-specific template references must be removed only after controlled acceptance;
- issue #14 and draft PR #15 must point to repository evidence, not substitute for it;
- PR #15 remains draft until actual code + controlled evidence are complete.