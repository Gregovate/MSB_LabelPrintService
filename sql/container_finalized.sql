/* ======================================================================
   File: container_finalize.sql
   Purpose:
     Finalize a completed container print batch.

   Behavior:
     1. Write one history row per container in the batch
     2. Mark batch item rows printed
     3. Clear ref.container.print_label only for containers in this batch
     4. Mark batch header COMPLETED

   Parameter:
     %(batch_id)s

   Author: Greg Liebig / Engineering Innovations, LLC
   Date: 2026-03-21
   ====================================================================== */

INSERT INTO ops.container_label_print (
    container_id,
    printed_at,
    printed_by_person_id,
    printed_by_text,
    print_method,
    label_orientation,
    label_qty,
    qr_url,
    container_label,
    notes
)
SELECT
    i.container_id,
    now(),
    b.started_by_person_id,
    b.started_by_text,
    'POLLING_SERVICE',
    i.label_orientation,
    2,
    i.qr_url,
    i.container_label,
    'Printed from container batch ' || b.container_label_batch_id
FROM ops.container_label_batch_item i
JOIN ops.container_label_batch b
  ON b.container_label_batch_id = i.container_label_batch_id
WHERE i.container_label_batch_id = %(batch_id)s;

UPDATE ops.container_label_batch_item
SET printed_flag = true,
    printed_at   = now()
WHERE container_label_batch_id = %(batch_id)s;

UPDATE ref.container c
SET print_label = false
WHERE EXISTS (
    SELECT 1
    FROM ops.container_label_batch_item i
    WHERE i.container_label_batch_id = %(batch_id)s
      AND i.container_id = c.container_id
);

UPDATE ops.container_label_batch
SET status = 'COMPLETED',
    batch_completed_at = now()
WHERE container_label_batch_id = %(batch_id)s;