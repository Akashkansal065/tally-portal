-- ============================================================
-- Open Tally-Clone : Schema Extension — Batch / Serial / Expiry Tracking
-- Depends on: schema.sql (stock_items, stock_entries, godowns, vouchers)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- Not every item needs tracking (e.g. loose nails don't need serials;
-- most items don't need batches). This flag lets the app show/hide
-- batch or serial fields per item rather than forcing it everywhere.
ALTER TABLE stock_items
    ADD COLUMN tracking_type ENUM('None','Batch','Serial') DEFAULT 'None' AFTER reorder_level,
    ADD COLUMN shelf_life_days INT NULL AFTER tracking_type;   -- used to auto-suggest expiry_date when a new batch is created

-- ------------------------------------------------------------
-- 1. BATCHES (for items tracked by batch/lot — pharma, food, chemicals)
-- ------------------------------------------------------------
CREATE TABLE batches (
    batch_id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id           INT NOT NULL,
    stock_item_id        INT NOT NULL,
    batch_number         VARCHAR(50) NOT NULL,
    manufacture_date     DATE,
    expiry_date          DATE,
    quantity_received    DECIMAL(14,3) NOT NULL,
    quantity_available   DECIMAL(14,3) NOT NULL,     -- decremented as batch is consumed; kept in sync via app logic
    purchase_voucher_id  BIGINT NULL,                 -- voucher that brought this batch into stock
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(stock_item_id),
    FOREIGN KEY (purchase_voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    UNIQUE KEY uq_batch_number (stock_item_id, batch_number)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. SERIAL NUMBERS (for items tracked individually — electronics,
--    appliances, machinery, anything under individual warranty)
-- ------------------------------------------------------------
CREATE TABLE serial_numbers (
    serial_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id           INT NOT NULL,
    stock_item_id        INT NOT NULL,
    serial_number        VARCHAR(80) NOT NULL,
    godown_id            INT NULL,                    -- current location; NULL once sold
    status               ENUM('Available','Sold','Returned','Damaged','In Transit') DEFAULT 'Available',
    purchase_voucher_id  BIGINT NULL,
    sale_voucher_id      BIGINT NULL,
    warranty_expiry      DATE NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(stock_item_id),
    FOREIGN KEY (godown_id) REFERENCES godowns(godown_id) ON DELETE SET NULL,
    FOREIGN KEY (purchase_voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    FOREIGN KEY (sale_voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    UNIQUE KEY uq_serial_number (stock_item_id, serial_number)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. LINK stock_entries TO THE SPECIFIC BATCH/SERIAL MOVED
-- ------------------------------------------------------------
-- A Sales voucher's stock_entries row for a batch-tracked item must
-- say WHICH batch was sold (for FEFO — First-Expiry-First-Out — and
-- for recall traceability). Serial-tracked items reference one specific unit.
ALTER TABLE stock_entries
    ADD COLUMN batch_id BIGINT NULL AFTER godown_id,
    ADD COLUMN serial_id BIGINT NULL AFTER batch_id,
    ADD CONSTRAINT fk_stock_entry_batch FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_stock_entry_serial FOREIGN KEY (serial_id) REFERENCES serial_numbers(serial_id) ON DELETE SET NULL;

-- ------------------------------------------------------------
-- Indexes — expiry alerts and traceability are the main query patterns
-- ------------------------------------------------------------
CREATE INDEX idx_batches_expiry ON batches (company_id, expiry_date);
CREATE INDEX idx_batches_item ON batches (stock_item_id, quantity_available);
CREATE INDEX idx_serial_status ON serial_numbers (stock_item_id, status);
CREATE INDEX idx_serial_warranty ON serial_numbers (warranty_expiry);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application flow notes:
-- - Purchase voucher for a Batch-tracked item: app prompts for batch
--   number + mfg/expiry date -> creates a `batches` row, links via
--   stock_entries.batch_id.
-- - Sales voucher for a Batch-tracked item: app suggests batches
--   ordered by expiry_date ascending (FEFO) so oldest stock clears first;
--   user can override. quantity_available on the chosen batch decrements.
-- - Purchase voucher for a Serial-tracked item: app creates one
--   `serial_numbers` row per unit received (qty must be whole numbers).
-- - Sales voucher for a Serial-tracked item: user picks specific
--   serial(s) to sell; status flips to 'Sold', sale_voucher_id set.
-- - "Expiring Soon" / "Near-Expiry Stock" report: simple query on
--   batches WHERE expiry_date BETWEEN NOW() AND NOW() + INTERVAL 30 DAY
--   AND quantity_available > 0.
-- ------------------------------------------------------------
