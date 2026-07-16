-- ============================================================
-- Open Tally-Clone : Schema Extension — Admin Panel & Permissions
-- Depends on: schema.sql (roles, users, permissions, companies)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. MODULES REGISTRY (drives the admin panel's permission matrix
--    dynamically instead of hardcoding module names in the UI)
-- ------------------------------------------------------------
CREATE TABLE modules (
    module_id           INT AUTO_INCREMENT PRIMARY KEY,
    code                VARCHAR(50) NOT NULL UNIQUE,   -- 'ledgers','vouchers','inventory','orders','reports','payments','users','roles','settings'
    name                VARCHAR(100) NOT NULL,
    description         VARCHAR(255),
    is_system           BOOLEAN DEFAULT TRUE           -- system modules can't be deleted from admin panel
) ENGINE=InnoDB;

INSERT INTO modules (code, name, description) VALUES
('ledgers',   'Ledgers & Groups',      'Chart of accounts management'),
('vouchers',  'Vouchers',              'Payment, Receipt, Journal, Sales, Purchase, etc.'),
('inventory', 'Inventory',             'Stock items, godowns, stock movement'),
('orders',    'Orders',                'Sales and Purchase orders'),
('payments',  'Payments & Bills',      'Bill-wise allocation, outstanding, gateway payments'),
('reports',   'Reports',               'Trial Balance, P&L, Balance Sheet, GST reports'),
('users',     'User Management',       'Create/manage users'),
('roles',     'Roles & Permissions',   'Manage roles and permission matrix'),
('settings',  'Company Settings',      'Company profile, GST config, gateway config, feature toggles');

-- Re-point permissions.module (free text) at the modules table properly.
-- (In a real Alembic migration this would be a data-preserving ALTER;
-- shown here as the target end-state.)
ALTER TABLE permissions
    ADD COLUMN module_id INT NULL AFTER role_id,
    ADD CONSTRAINT fk_permissions_module FOREIGN KEY (module_id) REFERENCES modules(module_id);

-- ------------------------------------------------------------
-- 2. PER-USER PERMISSION OVERRIDES
-- ------------------------------------------------------------
-- Role-level permissions cover 90% of cases, but admins frequently need
-- one-off exceptions: "this DataEntry user can also approve GST reports"
-- or "revoke this Accountant's delete access temporarily". Overrides
-- win over role permissions when present; NULL fields fall back to role.
CREATE TABLE user_permission_overrides (
    override_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    module_id           INT NOT NULL,
    can_create          BOOLEAN NULL,
    can_read            BOOLEAN NULL,
    can_update          BOOLEAN NULL,
    can_delete          BOOLEAN NULL,
    reason              VARCHAR(255),
    granted_by          INT NOT NULL,
    granted_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at          TIMESTAMP NULL,               -- e.g. temporary elevated access
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(module_id),
    FOREIGN KEY (granted_by) REFERENCES users(user_id),
    UNIQUE KEY uq_user_module_override (user_id, module_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. DATA-LEVEL SCOPING (restrict a user to specific godowns/cost
--    centers, not just module-level CRUD)
-- ------------------------------------------------------------
-- e.g. a warehouse clerk should only see/edit stock for their godown,
-- a regional accountant only their cost center.
CREATE TABLE user_data_scopes (
    scope_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    scope_type          ENUM('Godown','CostCenter','VoucherType') NOT NULL,
    scope_ref_id        INT NOT NULL,                 -- godown_id / cost_center_id / voucher_type_id depending on scope_type
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_scope (user_id, scope_type, scope_ref_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. APPROVAL WORKFLOWS (maker-checker — critical for a real admin
--    panel: e.g. "Payment vouchers above 50,000 need Admin approval")
-- ------------------------------------------------------------
CREATE TABLE approval_rules (
    rule_id             INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    module_id           INT NOT NULL,
    voucher_type_id     INT NULL,                     -- NULL = applies to all voucher types in the module
    condition_field     VARCHAR(50) DEFAULT 'total_amount',
    condition_operator  ENUM('>','>=','<','<=','=') DEFAULT '>',
    condition_value     DECIMAL(18,2) NOT NULL,
    approver_role_id    INT NOT NULL,                 -- who is allowed to approve
    is_active           BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(module_id),
    FOREIGN KEY (voucher_type_id) REFERENCES voucher_types(voucher_type_id),
    FOREIGN KEY (approver_role_id) REFERENCES roles(role_id)
) ENGINE=InnoDB;

CREATE TABLE approval_requests (
    request_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    rule_id             INT NOT NULL,
    voucher_id          BIGINT NOT NULL,
    requested_by        INT NOT NULL,
    status              ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    acted_by            INT NULL,
    comments            VARCHAR(500),
    requested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acted_at            TIMESTAMP NULL,
    FOREIGN KEY (rule_id) REFERENCES approval_rules(rule_id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    FOREIGN KEY (requested_by) REFERENCES users(user_id),
    FOREIGN KEY (acted_by) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. USER SESSIONS (admin panel needs to see & revoke active logins)
-- ------------------------------------------------------------
CREATE TABLE user_sessions (
    session_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    token_hash          VARCHAR(255) NOT NULL,        -- hashed JWT/refresh token, never store raw
    ip_address          VARCHAR(45),
    user_agent          VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at          TIMESTAMP NOT NULL,
    revoked_at          TIMESTAMP NULL,               -- admin can force-revoke ("log this user out everywhere")
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 6. COMPANY-LEVEL FEATURE TOGGLES / SETTINGS
-- ------------------------------------------------------------
-- Generic key-value so the admin panel can expose toggles without
-- schema changes every time a new setting is needed.
CREATE TABLE company_settings (
    setting_id          INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    setting_key         VARCHAR(100) NOT NULL,        -- 'allow_backdated_entries','session_timeout_minutes','require_approval_for_deletion'
    setting_value       VARCHAR(500) NOT NULL,
    updated_by          INT NOT NULL,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    UNIQUE KEY uq_company_setting (company_id, setting_key)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------
CREATE INDEX idx_overrides_user ON user_permission_overrides (user_id);
CREATE INDEX idx_scopes_user ON user_data_scopes (user_id, scope_type);
CREATE INDEX idx_approval_requests_status ON approval_requests (status);
CREATE INDEX idx_sessions_user ON user_sessions (user_id, revoked_at);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Effective-permission resolution order (implemented in FastAPI
-- as a single `get_effective_permission(user, module)` function,
-- called by a dependency/middleware on every protected route):
--
--   1. Check user_permission_overrides for (user_id, module_id).
--      Any non-NULL field here wins outright.
--   2. Fall back to permissions for the user's role_id + module_id.
--   3. Fall back to `can_read = TRUE, everything else = FALSE` if
--      neither row exists (fail safe, not fail open).
--   4. If user_data_scopes rows exist for this user + scope_type,
--      additionally filter query results to only those scope_ref_ids
--      (e.g. WHERE godown_id IN (user's allowed godowns)).
--
-- Admin panel screens this enables:
--   - Roles & Permissions: matrix of role x module x CRUD checkboxes
--   - Users: create/deactivate, assign role, grant per-user overrides,
--            assign data scopes, force-logout (revoke sessions)
--   - Approval Rules: set thresholds per voucher type, pick approver role
--   - Approval Inbox: pending approval_requests for the logged-in approver
--   - Settings: company_settings as toggles/inputs
--   - Audit Log Viewer: reads audit_logs (from schema.sql) with filters
-- ------------------------------------------------------------
