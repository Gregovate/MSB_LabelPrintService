/* ======================================================================
   File: display_finalized.sql
   Purpose:
     Finalize a completed display print batch.

   Behavior:
     1. Write one history row per display in the batch
     2. Mark batch item rows printed
     3. Clear ref.display.print_label only for displays in this batch
     4. Mark batch header COMPLETED

   Parameter:
     %(batch_id)s

   Author: Greg Liebig / Engineering Innovations, LLC
   Date: 2026-03-21
   ====================================================================== */

INSERT INTO ops.display_label_print (
    display_id,
    printed_at,
    printed_by_person_id,
    printed_by_text,
    print_method,
    label_qty,
    qr_url,
    line1,
    line2,
    notes
)
SELECT
    i.display_id,
    now(),
    b.started_by_person_id,
    b.started_by_text,
    'POLLING_SERVICE',
    1,
    i.qr_url,
    i.line1,
    i.line2,
    'Printed from display batch ' || b.display_label_batch_id
FROM ops.display_label_batch_item i
JOIN ops.display_label_batch b
  ON b.display_label_batch_id = i.display_label_batch_id
WHERE i.display_label_batch_id = %(batch_id)s;

UPDATE ops.display_label_batch_item
SET printed_flag = true,
    printed_at   = now()
WHERE display_label_batch_id = %(batch_id)s;

UPDATE ref.display d
SET print_label = false
WHERE EXISTS (
    SELECT 1
    FROM ops.display_label_batch_item i
    WHERE i.display_label_batch_id = %(batch_id)s
      AND i.display_id = d.display_id
);

UPDATE ops.display_label_batch
SET status = 'COMPLETED',
    batch_completed_at = now()
WHERE display_label_batch_id = %(batch_id)s;