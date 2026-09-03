/*
  Finalize one successfully printed Controller batch.

  The request flag and cached summary are updated only for Controllers frozen
  into this exact batch. Requests created after the snapshot remain pending.
*/

UPDATE ops.controller_label_batch_item
SET printed_flag = true,
    printed_at = now()
WHERE controller_label_batch_id = %(batch_id)s;

UPDATE ref.controller AS c
SET print_label = false
WHERE EXISTS (
    SELECT 1
    FROM ops.controller_label_batch_item AS i
    WHERE i.controller_label_batch_id = %(batch_id)s
      AND i.controller_id = c.controller_id
);

UPDATE ops.controller_label_batch
SET status = 'COMPLETED',
    batch_completed_at = now()
WHERE controller_label_batch_id = %(batch_id)s;

UPDATE ref.controller AS c
SET
    label_print_count_cached =
        COALESCE(c.label_print_count_cached, 0) + x.print_count,
    label_print_last_at_cached = GREATEST(
        COALESCE(
            c.label_print_last_at_cached,
            '1900-01-01'::timestamptz
        ),
        x.last_printed_at
    ),
    label_print_last_by_cached_id = x.started_by_person_id
FROM (
    SELECT
        i.controller_id,
        COUNT(*)::integer AS print_count,
        MAX(b.batch_completed_at) AS last_printed_at,
        MAX(b.started_by_person_id) AS started_by_person_id
    FROM ops.controller_label_batch_item AS i
    JOIN ops.controller_label_batch AS b
      ON b.controller_label_batch_id = i.controller_label_batch_id
    WHERE i.controller_label_batch_id = %(batch_id)s
    GROUP BY i.controller_id
) AS x
WHERE c.controller_id = x.controller_id;
