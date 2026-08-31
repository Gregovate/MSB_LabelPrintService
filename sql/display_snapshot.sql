/* ======================================================================
   Snapshot selected displays into a batch.
    display_snapshot.sql
   Parameters:
     %(batch_id)s
   ====================================================================== */

INSERT INTO ops.display_label_batch_item (
    display_label_batch_id,
    display_id,
    container_id,
    display_name,
    qr_url,
    line1,
    line2
)
SELECT
    %(batch_id)s,
    d.display_id,
    d.container_id,
    d.display_name,
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

FROM ref.display d
WHERE d.print_label = true
ON CONFLICT (display_label_batch_id, display_id) DO NOTHING;