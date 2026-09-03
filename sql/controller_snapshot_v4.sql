/*
  Snapshot the exact pending Controller request set into one immutable batch.

  Parameters:
    %(batch_id)s
    %(controller_ids)s
*/

INSERT INTO ops.controller_label_batch_item (
    controller_label_batch_id,
    controller_id,
    qr_url,
    line1
)
SELECT
    %(batch_id)s,
    c.controller_id,
    'https://db.sheboyganlights.org/scan/CTRL/' || c.controller_id,
    'CTRL:' || c.controller_id
FROM ref.controller AS c
JOIN ref.label_template AS lt
  ON lt.label_template_id = c.label_template_id
WHERE c.print_label = true
  AND c.controller_id = ANY(%(controller_ids)s)
  AND lt.label_template_code = 'QR_24MM_HORIZONTAL'
ON CONFLICT (controller_label_batch_id, controller_id) DO NOTHING;
