# Container QR Physical Acceptance — 2026-09-01

| Document Control | Value |
|---|---|
| Status | CURRENT ACCEPTANCE EVIDENCE — v4 still under controlled acceptance |
| System | MSB Label Print Service / PT-P950NW |
| Branch | `agent/runtime-preflight-hardening` |
| Related Issue | LabelPrintService #14 |
| Date | 2026-09-01 |

## Purpose

This document captures the physical Container-label findings discovered during controlled v4 acceptance. These findings are part of the LabelPrintService rendering contract and must not exist only in chat or GitHub issue comments.

## Accepted v4 Container data contract

For a selected Container, v4 exports and renders the following logical data:

```text
container_id
container_type_id
container_label
qr_url
```

For v4 Container rows, `qr_url` is retained as the historical database/batch column name but contains the actual compact machine payload rather than a literal URL.

Example:

```text
container_id       = 131
container_label    = C131
qr_url             = CONT:131
```

The generic Container LBX object contract is:

```text
objLine1 <- container_label
objQr    <- qr_url
```

Therefore the physical template receives:

```text
objLine1 = C131
objQr    = CONT:131
```

## Compact payload remains required

New/replacement Container labels printed by v4 use:

```text
CONT:<container_id>
```

Existing deployed full-URL Container labels remain valid and supported. There is no mass-relabel requirement solely to change payload format.

Controlled Zebra DS3678-ER Bluetooth-HID testing showed why the compact payload is operationally important:

- the scanner decodes both long URLs and compact identities quickly;
- the delay is the HID keyboard transmission after decode;
- full Container URLs are roughly 40+ characters and take materially longer to inject into a phone/tablet;
- compact values such as `CONT:4`, `CONT:24`, and `LOC:RB04-C-01` transmit quickly and remained intact during rapid field tests;
- rapid back-to-back scans can corrupt/interleave long HID keyboard transmissions if a new scan starts before the prior payload finishes;
- compact identities materially reduce that exposure window.

LabelPrintService must therefore not revert v4 Container labels to full URLs merely to make the QR symbol larger.

## QR Version finding

The first compact v4 Container acceptance print appeared physically much smaller than the intended 36 mm design even though the correct 36 mm tape was loaded and printer preflight passed.

Direct printing of the same LBX from Brother P-touch Editor proved the LBX page/layout and printer media were not being globally scaled down by v4 or b-PAC.

The actual cause was the QR symbol version selected for the short payload:

```text
CONT:131
```

With the short compact data, P-touch generated a **QR Version 2** symbol. At the configured cell size, Version 2 occupied much less physical area than the previous long-URL QR.

The accepted physical correction is to configure the Container QR object as:

```text
QR Version: 4
Error correction: 15%
```

Version 4 preserves the compact payload while maintaining the intended physical QR size on the 36 mm label.

Do not solve this by returning to the long URL.

## Horizontal 36 mm acceptance result

After setting the Container QR object to Version 4 with 15% error correction:

- a direct P-touch Editor print produced the intended large QR/text layout;
- a v4 print of the same logical Container data matched the Brother/P-touch physical scale;
- v4 produced the expected **two physical Container labels** for one selected Container;
- the compact payload remained `CONT:<container_id>`.

The earlier small print is therefore classified as a QR-version/template-setting problem, not a v4 print-engine scaling defect.

## Vertical template requirement

The 36 mm vertical Container template must use the same compact-payload QR sizing rule. Before vertical Container printing is accepted, verify that:

- `QR_label_1_line_vert_36mm.lbx` uses the accepted fixed QR Version 4 / 15% error-correction setting;
- the physical result fills the intended label area;
- v4 renders the same scale as a direct P-touch Editor comparison print;
- the printed compact payload scans correctly.

## Two-label physical-placement rationale

Current v4 Container behavior remains two physical labels per selected Container.

Field testing identified a practical placement rationale for the two copies:

- a lower Container QR gives the DS3678-ER a better face-on angle and improved practical scan geometry at distance;
- an upper Container QR remains useful as a fallback when snow, grass, debris, or other ground-level obstruction covers the lower label.

Both copies represent the same permanent Container identity and must encode the same `CONT:<container_id>` payload. Placement is an operator/Setup procedure; LabelPrintService does not encode different identities for the two copies.

## Compatibility boundary

This Container-first compact migration does not automatically change Display payloads.

Current v4 rule remains:

```text
Container new/replacement label -> CONT:<container_id>
Display new/replacement label   -> existing full scan URL unless separately approved
```

A later Display compact-payload migration may be justified by the same Bluetooth-HID evidence, but it is not silently implied by this Container acceptance record.

## Acceptance still remaining

This document records the physical QR-size finding and horizontal print comparison. It does not by itself close LabelPrintService #14.

Remaining acceptance work includes the other v4 gates tracked by the primary architecture/acceptance contract, including vertical-template proof and outstanding printer/operator recovery behavior.
