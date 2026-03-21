/* ======================================================================
   MSB Label Batch Tables
   Purpose:
     Create snapshot batch tables used by the polling print service.

   Notes:
     - Snapshot rows are captured at batch start.
     - Only snapshot rows are finalized/cleared after success.
     - New selections made during printing remain untouched.

   Author: Greg Liebig / Engineering Innovations, LLC
   Date: 2026-03-20
   ====================================================================== */

BEGIN;

-- ============================================================
-- DISPLAY BATCH HEADER
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.display_label_batch (
    display_label_batch_id BIGSERIAL PRIMARY KEY,
    batch_started_at       timestamptz NOT NULL DEFAULT now(),
    batch_completed_at     timestamptz,
    started_by_person_id   integer,
    started_by_text        text,
    status                 text NOT NULL DEFAULT 'PENDING',
    notes                  text
);

CREATE INDEX IF NOT EXISTS idx_display_label_batch_status
ON ops.display_label_batch(status);

ALTER TABLE ops.display_label_batch
DROP CONSTRAINT IF EXISTS fk_display_label_batch_person;

ALTER TABLE ops.display_label_batch
ADD CONSTRAINT fk_display_label_batch_person
FOREIGN KEY (started_by_person_id)
REFERENCES ref.person(person_id)
ON UPDATE CASCADE
ON DELETE SET NULL;


-- ============================================================
-- DISPLAY BATCH ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.display_label_batch_item (
    display_label_batch_item_id BIGSERIAL PRIMARY KEY,
    display_label_batch_id      bigint NOT NULL,
    display_id                  integer NOT NULL,
    container_id                integer,
    display_name                text,
    qr_url                      text,
    line1                       text,
    line2                       text,
    printed_flag                boolean NOT NULL DEFAULT false,
    printed_at                  timestamptz
);

ALTER TABLE ops.display_label_batch_item
DROP CONSTRAINT IF EXISTS fk_display_label_batch_item_batch;

ALTER TABLE ops.display_label_batch_item
ADD CONSTRAINT fk_display_label_batch_item_batch
FOREIGN KEY (display_label_batch_id)
REFERENCES ops.display_label_batch(display_label_batch_id)
ON DELETE CASCADE;

ALTER TABLE ops.display_label_batch_item
DROP CONSTRAINT IF EXISTS fk_display_label_batch_item_display;

ALTER TABLE ops.display_label_batch_item
ADD CONSTRAINT fk_display_label_batch_item_display
FOREIGN KEY (display_id)
REFERENCES ref.display(display_id)
ON UPDATE CASCADE
ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_display_label_batch_item_batch_display'
    ) THEN
        ALTER TABLE ops.display_label_batch_item
        ADD CONSTRAINT uq_display_label_batch_item_batch_display
        UNIQUE (display_label_batch_id, display_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_display_label_batch_item_batch
ON ops.display_label_batch_item(display_label_batch_id);


-- ============================================================
-- CONTAINER BATCH HEADER
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.container_label_batch (
    container_label_batch_id BIGSERIAL PRIMARY KEY,
    batch_started_at         timestamptz NOT NULL DEFAULT now(),
    batch_completed_at       timestamptz,
    started_by_person_id     integer,
    started_by_text          text,
    status                   text NOT NULL DEFAULT 'PENDING',
    notes                    text
);

CREATE INDEX IF NOT EXISTS idx_container_label_batch_status
ON ops.container_label_batch(status);

ALTER TABLE ops.container_label_batch
DROP CONSTRAINT IF EXISTS fk_container_label_batch_person;

ALTER TABLE ops.container_label_batch
ADD CONSTRAINT fk_container_label_batch_person
FOREIGN KEY (started_by_person_id)
REFERENCES ref.person(person_id)
ON UPDATE CASCADE
ON DELETE SET NULL;


-- ============================================================
-- CONTAINER BATCH ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.container_label_batch_item (
    container_label_batch_item_id BIGSERIAL PRIMARY KEY,
    container_label_batch_id      bigint NOT NULL,
    container_id                  integer NOT NULL,
    container_type_id             integer,
    qr_url                        text,
    container_label               text,
    label_orientation             text NOT NULL,
    printed_flag                  boolean NOT NULL DEFAULT false,
    printed_at                    timestamptz
);

ALTER TABLE ops.container_label_batch_item
DROP CONSTRAINT IF EXISTS fk_container_label_batch_item_batch;

ALTER TABLE ops.container_label_batch_item
ADD CONSTRAINT fk_container_label_batch_item_batch
FOREIGN KEY (container_label_batch_id)
REFERENCES ops.container_label_batch(container_label_batch_id)
ON DELETE CASCADE;

ALTER TABLE ops.container_label_batch_item
DROP CONSTRAINT IF EXISTS fk_container_label_batch_item_container;

ALTER TABLE ops.container_label_batch_item
ADD CONSTRAINT fk_container_label_batch_item_container
FOREIGN KEY (container_id)
REFERENCES ref.container(container_id)
ON UPDATE CASCADE
ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_container_label_batch_item_batch_container'
    ) THEN
        ALTER TABLE ops.container_label_batch_item
        ADD CONSTRAINT uq_container_label_batch_item_batch_container
        UNIQUE (container_label_batch_id, container_id);
    END IF;
END $$;

ALTER TABLE ops.container_label_batch_item
DROP CONSTRAINT IF EXISTS ck_container_label_batch_item_orientation;

ALTER TABLE ops.container_label_batch_item
ADD CONSTRAINT ck_container_label_batch_item_orientation
CHECK (label_orientation IN ('VERTICAL', 'HORIZONTAL'));

CREATE INDEX IF NOT EXISTS idx_container_label_batch_item_batch
ON ops.container_label_batch_item(container_label_batch_id);

COMMIT;