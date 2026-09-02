/* ======================================================================
   Snapshot selected Containers into a v4 batch.
   QR payload remains the exact v3 full scan URL.
   Zebra ADF may shorten the transmitted scan data for HID workflows,
   but the physical QR payload itself remains backward-compatible.
   Parameters:
     %(batch_id)s
     %(container_ids)s
   ====================================================================== */

INSERT INTO ops.container_label_batch_item (
    container_label_batch_id,
    container_id,
    container_type_id,
    qr_url,
    container_label,
    label_orientation
)
SELECT
    %(batch_id)s,
    c.container_id,
    c.container_type_id,
    'https://db.sheboyganlights.org/scan/CONT/' || c.container_id AS qr_url,
    'C' || LPAD(c.container_id::text, 3, '0') AS container_label,
    CASE
        WHEN c.container_type_id = 1 THEN 'VERTICAL'
        ELSE 'HORIZONTAL'
    END AS label_orientation
FROM ref.container c
WHERE c.print_label = true
  AND c.container_id = ANY(%(container_ids)s)
ON CONFLICT (container_label_batch_id, container_id) DO NOTHING;