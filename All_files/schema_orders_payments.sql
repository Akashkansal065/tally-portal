-- ============================================================
-- Open Tally-Clone : Schema Extension — Orders & Bill-wise Payments
-- Depends on: schema.sql (companies, ledgers, vouchers, stock_items, godowns)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. SALES / PURCHASE ORDERS
-- ------------------------------------------------------------
-- These are commitments only — NO entries in voucher_entries or
-- stock_entries until (partially) converted into an actual
-- Sales/Purchase voucher. This mirrors Tally's "Order Vouchers"
-- which sit outside the accounting books until fulfilled.

CREATE TABLE orders (
    order_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    order_type          ENUM('Sales','Purchase') NOT NULL,
    order_number        VARCHAR(30) NOT NULL,
    order_date          DATE NOT NULL,
    party_ledger_id     INT NOT NULL,              -- customer (Sales) or vendor (Purchase)
    due_date            DATE,                       -- expected delivery/fulfillment date
    reference_number    VARCHAR(50),               -- e.g. customer's PO number
    narration           TEXT,
    status              ENUM('Open','Partially Fulfilled','Fulfilled','Cancelled') DEFAULT 'Open',
    total_amount        DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    created_by          INT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (party_ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    UNIQUE KEY uq_order_number (company_id, order_type, order_number)
) ENGINE=InnoDB;

CREATE TABLE order_items (
    order_item_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id            BIGINT NOT NULL,
    stock_item_id       INT NOT NULL,
    ordered_qty         DECIMAL(14,3) NOT NULL,
    fulfilled_qty       DECIMAL(14,3) NOT NULL DEFAULT 0,   -- running total as invoices are raised against this order
    rate                DECIMAL(14,2) NOT NULL,
    amount              DECIMAL(18,2) NOT NULL,
    due_date            DATE,                                -- per-line delivery date can differ from order-level
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(stock_item_id)
) ENGINE=InnoDB;

-- Links an actual Sales/Purchase voucher (invoice) back to the order(s)
-- it fulfills — an invoice can close out one order fully, one order
-- partially, or even draw from multiple orders (rare but valid).
CREATE TABLE order_fulfillments (
    fulfillment_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_item_id       BIGINT NOT NULL,
    voucher_id          BIGINT NOT NULL,           -- the Sales/Purchase voucher that fulfills this line
    fulfilled_qty        DECIMAL(14,3) NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. BILL-WISE PAYMENT ALLOCATION (the AR/AP tracking layer)
-- ------------------------------------------------------------
-- Every Sales/Purchase voucher entry against a party ledger becomes
-- an "outstanding bill". Every Payment/Receipt entry against that
-- same ledger can be allocated against one or more specific bills,
-- OR marked as Advance / On Account if there's nothing to match yet.

CREATE TABLE bills (
    bill_id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    party_ledger_id     INT NOT NULL,
    voucher_id          BIGINT NOT NULL,           -- the Sales/Purchase voucher that created this bill
    bill_reference      VARCHAR(50) NOT NULL,      -- usually same as invoice number, editable
    bill_date           DATE NOT NULL,
    due_date            DATE,                       -- for ageing / credit-period tracking
    bill_amount         DECIMAL(18,2) NOT NULL,
    settled_amount      DECIMAL(18,2) NOT NULL DEFAULT 0.00,   -- kept in sync via triggers or app logic
    status              ENUM('Open','Partially Settled','Settled') DEFAULT 'Open',
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (party_ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE bill_allocations (
    allocation_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    voucher_entry_id    BIGINT NOT NULL,           -- the Payment/Receipt entry doing the settling
    bill_id             BIGINT NULL,               -- NULL when allocation_type is Advance/On Account
    allocation_type     ENUM('Against Ref','Advance','On Account','New Ref') NOT NULL,
    amount              DECIMAL(18,2) NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (voucher_entry_id) REFERENCES voucher_entries(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Indexes for outstanding / ageing reports
-- ------------------------------------------------------------
CREATE INDEX idx_bills_party_status ON bills (party_ledger_id, status);
CREATE INDEX idx_bills_due_date ON bills (due_date);
CREATE INDEX idx_orders_status ON orders (company_id, order_type, status);
CREATE INDEX idx_bill_alloc_bill ON bill_allocations (bill_id);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application-layer rules (NOT enforced by MySQL, must be in FastAPI service layer):
-- 1. When a Sales/Purchase voucher is posted, auto-create a `bills` row.
-- 2. sum(bill_allocations.amount for a bill) must never exceed bills.bill_amount.
-- 3. bills.settled_amount and status are recalculated whenever a
--    bill_allocations row is inserted/updated/deleted.
-- 4. An order_item's status flips to 'Fulfilled' once fulfilled_qty == ordered_qty
--    across all its order_fulfillments rows; order.status is derived from its items.
-- ------------------------------------------------------------
