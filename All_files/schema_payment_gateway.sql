-- ============================================================
-- Open Tally-Clone : Schema Extension — Payment Gateway Integration
-- Depends on: schema.sql, schema_orders_payments.sql
-- Supports: Razorpay, Stripe (extensible to others via `gateway` enum)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. GATEWAY CONFIG (per company — a company may enable more than one)
-- ------------------------------------------------------------
-- IMPORTANT: never store the actual secret key in this table.
-- `secret_key_ref` is a pointer/name into an env var or secrets
-- manager (e.g. AWS Secrets Manager, Vault) — the app looks it up
-- at runtime. Only the public/publishable key is safe to store directly.
CREATE TABLE payment_gateway_configs (
    gateway_config_id   INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    gateway             ENUM('Razorpay','Stripe') NOT NULL,
    public_key          VARCHAR(255) NOT NULL,
    secret_key_ref       VARCHAR(100) NOT NULL,     -- e.g. "razorpay_secret_company_12"
    webhook_secret_ref  VARCHAR(100) NOT NULL,      -- for verifying webhook signatures
    is_active           BOOLEAN DEFAULT TRUE,
    is_test_mode        BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    UNIQUE KEY uq_company_gateway (company_id, gateway)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. PAYMENT LINKS (sent to customer for a specific bill/invoice)
-- ------------------------------------------------------------
CREATE TABLE payment_links (
    payment_link_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    bill_id             BIGINT NOT NULL,
    gateway_config_id   INT NOT NULL,
    gateway_link_id     VARCHAR(100),               -- Razorpay/Stripe's own link/session ID
    link_url            VARCHAR(500),
    amount              DECIMAL(18,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'INR',
    status              ENUM('Created','Sent','Paid','Expired','Cancelled') DEFAULT 'Created',
    expires_at          TIMESTAMP NULL,
    created_by          INT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (gateway_config_id) REFERENCES payment_gateway_configs(gateway_config_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. GATEWAY TRANSACTIONS (the actual payment attempt/result)
-- ------------------------------------------------------------
CREATE TABLE gateway_transactions (
    transaction_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id              INT NOT NULL,
    payment_link_id         BIGINT NULL,             -- NULL if paid via direct checkout, not a link
    bill_id                 BIGINT NOT NULL,
    gateway_config_id       INT NOT NULL,
    gateway_payment_id      VARCHAR(100) NOT NULL,   -- e.g. Razorpay pay_xxx / Stripe pi_xxx
    gateway_order_id        VARCHAR(100),            -- Razorpay order_xxx / Stripe checkout session id
    amount                  DECIMAL(18,2) NOT NULL,
    currency                VARCHAR(3) DEFAULT 'INR',
    status                  ENUM('Created','Authorized','Captured','Failed','Refunded','Partially Refunded') NOT NULL,
    failure_reason          VARCHAR(255),
    method                  VARCHAR(30),             -- card, upi, netbanking, wallet
    voucher_id              BIGINT NULL,             -- Receipt voucher auto-created once Captured (links back to schema.sql vouchers)
    raw_payload             JSON,                     -- full gateway response, kept for audit/dispute resolution
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (payment_link_id) REFERENCES payment_links(payment_link_id) ON DELETE SET NULL,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id),
    FOREIGN KEY (gateway_config_id) REFERENCES payment_gateway_configs(gateway_config_id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    UNIQUE KEY uq_gateway_payment (gateway_config_id, gateway_payment_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. WEBHOOK EVENT LOG (idempotency + audit trail for incoming webhooks)
-- ------------------------------------------------------------
-- Gateways retry webhooks on failure/timeout — this table's unique
-- key on (gateway, gateway_event_id) is what prevents double-processing
-- the same event into two Receipt vouchers.
CREATE TABLE webhook_events (
    webhook_event_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    gateway_config_id   INT NOT NULL,
    gateway_event_id    VARCHAR(150) NOT NULL,      -- gateway's own event/idempotency ID
    event_type          VARCHAR(60) NOT NULL,       -- e.g. payment.captured, checkout.session.completed
    payload             JSON NOT NULL,
    signature_verified  BOOLEAN DEFAULT FALSE,
    processed           BOOLEAN DEFAULT FALSE,
    processing_error    VARCHAR(500),
    received_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at        TIMESTAMP NULL,
    FOREIGN KEY (gateway_config_id) REFERENCES payment_gateway_configs(gateway_config_id) ON DELETE CASCADE,
    UNIQUE KEY uq_gateway_event (gateway_config_id, gateway_event_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------
CREATE INDEX idx_payment_links_bill ON payment_links (bill_id, status);
CREATE INDEX idx_gateway_txn_bill ON gateway_transactions (bill_id, status);
CREATE INDEX idx_webhook_processed ON webhook_events (processed, received_at);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application flow (implemented in FastAPI service layer):
--
-- 1. Generate link:  POST /bills/{id}/payment-link
--    -> calls gateway API (Razorpay Payment Links / Stripe Checkout Session)
--    -> stores row in `payment_links`, sends URL to customer (email/SMS)
--
-- 2. Customer pays on gateway's hosted page (never touches our server
--    with card data — PCI scope stays with the gateway).
--
-- 3. Gateway sends webhook -> POST /webhooks/{gateway}
--    a. Verify signature using webhook_secret_ref
--    b. Insert into `webhook_events` (unique constraint = idempotency guard)
--    c. If event_type indicates success (payment.captured / checkout.session.completed):
--       - Insert/update `gateway_transactions` row, status = 'Captured'
--       - Auto-create a Receipt voucher (schema.sql: vouchers + voucher_entries)
--         crediting the party ledger, debiting the Bank/Gateway-clearing ledger
--       - Insert `bill_allocations` row, allocation_type = 'Against Ref',
--         linking the new voucher_entry to the original `bill_id`
--       - Recalculate `bills.settled_amount` / `status`
--       - Mark `payment_links.status` = 'Paid'
--
-- 4. Reconciliation report compares `gateway_transactions` against the
--    gateway's settlement report (payout batch) to catch any mismatches
--    (e.g. gateway fees deducted, refunds, chargebacks).
-- ------------------------------------------------------------
