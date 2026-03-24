/* ======================================================================
   File: container_finalize.sql

   Purpose:
     Finalize a completed container print batch.

   Behavior (Current — v3 design):
     1. Mark batch item rows printed
     2. Clear ref.container.print_label only for containers in this batch
     3. Update cached print summary fields on ref.container
     4. Mark batch header COMPLETED

   Parameter:
     %(batch_id)s

   ----------------------------------------------------------------------
   CHANGE LOG
   ----------------------------------------------------------------------
   2026-03-22 — Greg Liebig / Engineering Innovations, LLC
     • REMOVED legacy history insert into ops.container_label_print
       (eliminates redundant data storage)
     • Batch + Batch_Item tables are now the single source of truth
     • ADDED cached field updates on ref.container:
         - label_print_count_cached
         - label_print_last_at_cached
     • Container cached counts are derived as physical labels printed:
         COUNT(*) * 2
     • Prevents polling service from writing to legacy tables

   2026-03-21 — Greg Liebig / Engineering Innovations, LLC
     • Initial polling service batch finalization logic
     • Included legacy history insert (now removed)

   ----------------------------------------------------------------------

   Author: Greg Liebig / Engineering Innovations, LLC
   ====================================================================== */

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

UPDATE ref.container c
SET
    label_print_count_cached =
        COALESCE(c.label_print_count_cached, 0) + x.print_count,

    label_print_last_at_cached =
        GREATEST(
            COALESCE(c.label_print_last_at_cached,
                     '1900-01-01'::timestamptz),
            x.last_printed_at
        )
FROM (
    SELECT
        i.container_id,
        (COUNT(*) * 2)::integer AS print_count,
        MAX(b.batch_completed_at) AS last_printed_at
    FROM ops.container_label_batch_item i
    JOIN ops.container_label_batch b
      ON b.container_label_batch_id = i.container_label_batch_id
    WHERE i.container_label_batch_id = %(batch_id)s
    GROUP BY i.container_id
) x
WHERE c.container_id = x.container_id;