/* ======================================================================
   Snapshot selected Containers into a v4 batch.
   v4 machine payload: CONT:<container_id>.
   Existing deployed full-URL labels remain supported by Scan.
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
    'CONT:' || c.container_id::text AS qr_url,
    'C' || LPAD(c.container_id::text, 3, '0') AS container_label,
    CASE
        WHEN c.container_type_id = 1 THEN 'VERTICAL'
        ELSE 'HORIZONTAL'
    END AS label_orientation
FROM ref.container c
WHERE c.print_label = true
  AND c.container_id = ANY(%(container_ids)s)
ON CONFLICT (container_label_batch_id, container_id) DO NOTHING;