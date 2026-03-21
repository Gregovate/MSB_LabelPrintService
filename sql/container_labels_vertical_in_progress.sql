/* ======================================================================
   Filename: container_labels_vertical.csv
   Purpose:
     Export in-progress container labels for the VERTICAL container
     template.

   Output headers:
     qr_url,container_label

   Rules:
     - container_test_status_id = 2 = In Progress
     - ref.container.label_required = true
     - container_type_id = 1 uses vertical template
     - quantity (2 labels per container) handled by print workflow

   Author: Greg Liebig / Engineering Innovations, LLC
   Date: 2026-03-19
   output file (Greg's PC) C:\MSB_LabelService\data\container_labels_vertical.csv
   ====================================================================== */

SELECT
  'https://db.sheboyganlights.org/scan/CONT/' || c.container_id AS qr_url,
  'C' || LPAD(c.container_id::text, 3, '0') AS container_label
FROM ops.test_session ts
JOIN ref.container c
  ON c.container_id = ts.container_id
WHERE ts.container_test_status_id = 2
  AND c.label_required = true
  AND c.container_type_id = 1
ORDER BY c.container_id;