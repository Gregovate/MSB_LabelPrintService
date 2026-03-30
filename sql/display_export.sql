/* ======================================================================
   Export display batch rows for CSV creation.
   display)export.sql
   Parameters:
     %(batch_id)s
   ====================================================================== */

SELECT
    display_id,
    container_id,
    display_name,
    line1,
    line2,
    qr_url
FROM ops.display_label_batch_item
WHERE display_label_batch_id = %(batch_id)s
ORDER BY container_id, display_name, display_id;