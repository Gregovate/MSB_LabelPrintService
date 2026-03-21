/* ======================================================================
   Export horizontal container batch rows for CSV creation.
   Parameters:
     %(batch_id)s
   ====================================================================== */

SELECT
    container_id,
    container_type_id,
    container_label,
    qr_url
FROM ops.container_label_batch_item
WHERE container_label_batch_id = %(batch_id)s
  AND label_orientation = 'HORIZONTAL'
ORDER BY container_id;