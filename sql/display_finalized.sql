/* ======================================================================
   File: display_finalized.sql
   Purpose:
     Finalize a completed display print batch.

   Behavior:
     1. Mark batch item rows printed
     2. Clear ref.display.print_label only for displays in this batch
     3. Update cached print summary fields on ref.display
     4. Mark batch header COMPLETED

   Parameter:
     %(batch_id)s

   ----------------------------------------------------------------------
   CHANGE LOG
   ----------------------------------------------------------------------
   2026-03-22 — Greg Liebig / Engineering Innovations, LLC
     • REMOVED legacy history insert into ops.display_label_print
       (eliminates redundant data storage)
     • Batch + Batch_Item tables are now the single source of truth
     • ADDED cached field updates on ref.display:
         - label_print_count_cached
         - label_print_last_at_cached
     • Ensures Directus bookmarks show counts/dates without joins
     • Prevents polling service from writing to legacy tables

   2026-03-21 — Greg Liebig / Engineering Innovations, LLC
     • Initial polling service batch finalization logic
     • Included legacy history insert (now removed)

   ----------------------------------------------------------------------

   ====================================================================== */

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

UPDATE ref.display d
SET
    label_print_count_cached = d.label_print_count_cached + x.print_count,
    label_print_last_at_cached = GREATEST(
        COALESCE(d.label_print_last_at_cached, '1900-01-01'::timestamptz),
        x.last_printed_at
    )
FROM (
    SELECT
        i.display_id,
        COUNT(*)::integer AS print_count,
        MAX(b.batch_completed_at) AS last_printed_at
    FROM ops.display_label_batch_item i
    JOIN ops.display_label_batch b
      ON b.display_label_batch_id = i.display_label_batch_id
    WHERE i.display_label_batch_id = %(batch_id)s
    GROUP BY i.display_id
) x
WHERE d.display_id = x.display_id;