# 12 mm Wiring Label — Production Field-Data Evidence

| Document Control | Value |
|---|---|
| Document Type | Engineering Test Evidence |
| System | MSB Label Print Service / FieldWiring |
| Status | CURRENT — recovered from the 2026-09-01 sizing session |
| Controlling Issue | LabelPrintService #14 |
| Source View | `lor_snap.preview_wiring_fieldlead_v6` |

## Purpose

This record preserves the real production FieldWiring values used to size and test the 12 mm fold-over label. Test scripts must use the tracked fixture CSV derived from these rows, not invented placeholder text.

The physical label contract is:

```text
objChannel       / objChannel_right       <- zero-padded physical output
objLine1         / objLine1_right         <- split installer-facing line 1
objLine2         / objLine2_right         <- split installer-facing line 2
```

The right-side names are template bindings. They receive the same three logical values as the left side.

## Source Query

The following read-only query was run against the current FieldWiring field-lead view. It deliberately excludes raw LOR subprops and joins only permanent active Displays.

```sql
SELECT DISTINCT
    d.display_id,
    d.display_name,
    fw.channel_name,
    LENGTH(fw.channel_name) AS channel_name_length,
    fw.network,
    fw.controller,
    fw.start_channel AS output_plug
FROM lor_snap.preview_wiring_fieldlead_v6 AS fw
JOIN ref.display AS d
    ON d.display_name = fw.display_name
WHERE d.display_status_id = 1
  AND fw.channel_name IS NOT NULL
  AND BTRIM(fw.channel_name) <> ''
ORDER BY
    LENGTH(fw.channel_name) DESC,
    d.display_name,
    fw.channel_name
LIMIT 50;
```

## Recovered Result

```text
display_id | display_name                         | channel_name                                    | length | network | controller | output
1117       | WW-UncleLouis-Standing               | WW 39-08 UncleLouis Standing Pants Master Prop | 46     | Regular | 39         | 8
1114       | WW-ClarkGriswold                     | WW 39-03 Clark Sweater Fill Face Surprised     | 42     | Regular | 39         | 3
615        | HW-EventTrafficRight-01              | HWY-42 09-02 Event Traffic Right Lane 1        | 39     | Regular | 09         | 1
747        | FC-CarCounter-PS                     | Car Counter PS 1B-04 ArrowLeft-Dumb-03         | 38     | Regular | 1B         | 4
291        | QV-StationSign                       | QV 01-11 Santa's Station Sign Twist 01         | 38     | Regular | 01         | 11
291        | QV-StationSign                       | QV 01-12 Santa's Station Sign Twist 02         | 38     | Regular | 01         | 12
126        | TC-FryingSanta                       | TC Frying Santa 41 01-147 6 Grill fire         | 38     | Aux F   | 41         | 1
637        | GG-RalphieV2-34-01                   | GG34-v2-Ralphie Mouth AI (Full Open)           | 36     | Aux F   | 34         | 43
781        | PO-POSign                            | PO 24-01 North Pole Post Office Sign           | 36     | Regular | 24         | 1
637        | GG-RalphieV2-34-01                   | GG34-v2-Ralphie Mouth E (Half Open)            | 35     | Aux F   | 34         | 40
613        | PN-SchroederAndLucy                  | PN SL 79-16 Schroeder Arm Left Down            | 35     | Regular | 79         | 16
890        | SW-WorkshopSign                      | SW 66-01 Santa's Workshop Roof Sign            | 35     | Regular | 66         | 1
629        | GG-EldenV2-30-01                     | GG30-v2-Elden Mouth AI (Full Open)             | 34     | Aux F   | 30         | 43
624        | GG-FelixV2-32-01                     | GG32-v2-Felix Mouth AI (Full Open)             | 34     | Aux F   | 32         | 43
613        | PN-SchroederAndLucy                  | PN SL 79-13 Schroeder Arm Right Up             | 34     | Regular | 79         | 13
613        | PN-SchroederAndLucy                  | PN SL 79-14 Schroeder Arm Right Dn             | 34     | Regular | 79         | 14
899        | SW-PotterPole-Sign-01-NorthPole-Top  | PP 65-05 Sign 01 Potter North Pole             | 34     | Aux D   | 65         | 5
5          | TC-CarolerPanel-01                   | TC 7B-10 Caroler P2 Mouth Closed 1             | 34     | Regular | 7B         | 10
126        | TC-FryingSanta                       | TC Frying Santa 7D-06 Close handle             | 34     | Regular | 7D         | 6
126        | TC-FryingSanta                       | TC Frying Santa 7D-07 Tongue Right             | 34     | Regular | 7D         | 7
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 1          | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 10         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 11         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 12         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 13         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 14         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 15         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 16         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 17         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 18         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 19         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 2          | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 20         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 21         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 22         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 23         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 24         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 25         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 26         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 27         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 28         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 29         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 3          | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 30         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 31         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 32         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 33         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 34         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 35         | 1
125        | TR-MegaTreeRGBTree                   | MT Mega Tree RGB Tree 48 x 100-360             | 34     | Regular | 36         | 1
```

## Tracked Physical-Test Fixtures

`templates/pt_p950nw/csv/wiring_label_12mm_real_fieldlead_test.csv` contains the 11 selected installer-facing splits created from the result above:

```csv
output_plug,line1,line2
08,UncleLouis Standing,Pants Master Prop
03,Clark Sweater Fill,Face Surprised
01,Event Traffic Right,Lane 1
04,ArrowLeft-Dumb-03,
11,Santa's Station Sign,Twist 01
01,North Pole Post,Office Sign
16,Schroeder Arm Left,Down
01,Santa's Workshop,Roof Sign
05,Sign 01 Potter,North Pole
10,Caroler P2,Mouth Closed 1
06,Frying Santa,Close handle
```

The split fixture is physical-design evidence, not yet the governed production transformation algorithm. FieldWiring still needs an accepted rule for removing the technical controller/address prefix and splitting or trimming the remaining installer-facing text.

`output_plug` remains numeric business data. LabelPrintService formats the printed channel as two characters (`01` through `09`, then `10` and higher) so the label does not depend on CSV software preserving leading zeroes.

## Acceptance Use

The export and physical Wiring probes read this tracked CSV directly. Fixture row 1 is the default because it derives from the longest raw production name in the recovered result. Other rows can be selected with `--fixture-row N`.

Do not replace these values with invented stress-test strings. Add new production-derived fixtures here when a newly observed value exceeds the current field-length or layout envelope.
