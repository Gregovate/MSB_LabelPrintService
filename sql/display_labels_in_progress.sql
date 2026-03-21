/* ======================================================================
   Filename: MSB_Display_Labels_In_Progress.sql
   Purpose:
     Generate live display label data for displays currently in active
     test sessions.

   Output headers:
     qr_url,line1,line2

   Rules:
     - container_test_status_id = 2 = In Progress
     - only displays with ref.display.label_required = true
     - split after second hyphen only when full display_name exceeds
       20 characters
     - source tables:
         ops.test_session
         ops.display_test_session
         ref.display

   Notes:
     - This query is intended for label generation workflow
     - One label per eligible display
     - Does not yet handle print history / duplicate prevention

   Author: Greg Liebig / Engineering Innovations, LLC
   Date: 2026-03-19
   output file (Greg's PC) C:\MSB_LabelService\data\display_labels.csv
   ====================================================================== */

SELECT
  'https://db.sheboyganlights.org/scan/DISP/' || d.display_id AS qr_url,

  CASE
    WHEN LENGTH(d.display_name) <= 20 THEN d.display_name
    WHEN d.display_name ~ '^[^-]+-[^-]+-'
      THEN split_part(d.display_name, '-', 1) || '-' || split_part(d.display_name, '-', 2)
    ELSE d.display_name
  END AS line1,

  CASE
    WHEN LENGTH(d.display_name) <= 20 THEN ''
    WHEN d.display_name ~ '^[^-]+-[^-]+-'
      THEN SUBSTRING(
        d.display_name
        FROM LENGTH(split_part(d.display_name, '-', 1) || '-' || split_part(d.display_name, '-', 2)) + 1
      )
    ELSE ''
  END AS line2

FROM ops.test_session ts
JOIN ops.display_test_session dts
  ON dts.test_session_id = ts.test_session_id
JOIN ref.display d
  ON d.display_id = dts.display_id
WHERE ts.container_test_status_id = 2
  AND d.label_required = true
ORDER BY ts.container_id, d.display_name;