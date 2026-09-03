/* Export frozen Controller render intent for audit and b-PAC printing. */

SELECT
    controller_id,
    qr_url,
    line1
FROM ops.controller_label_batch_item
WHERE controller_label_batch_id = %(batch_id)s
ORDER BY controller_label_batch_item_id;
