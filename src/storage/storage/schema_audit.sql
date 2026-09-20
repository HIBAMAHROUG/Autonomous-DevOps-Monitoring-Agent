-- ============================================================
-- Schema PostgreSQL - Audit log & Approbations (US 4.1 / 4.2)
-- ============================================================

DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS approval_requests CASCADE;

-- AUDIT LOG
CREATE TABLE audit_log (
 id BIGSERIAL PRIMARY KEY,
 timestamp TEXT NOT NULL,
 action_id TEXT NOT NULL,
 success BOOLEAN NOT NULL,
 message TEXT NOT NULL
);

CREATE INDEX idx_audit_log_action_id ON audit_log(action_id);
CREATE INDEX idx_audit_log_id ON audit_log(id DESC);

-- APPROVAL REQUESTS
CREATE TABLE approval_requests (
 action_id TEXT PRIMARY KEY,
 executor TEXT NOT NULL,
 params JSONB NOT NULL DEFAULT '{}',
 severity TEXT NOT NULL,
 reason TEXT NOT NULL,
 requested_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
 decided_at TEXT,
 decided_by TEXT
);

CREATE INDEX idx_approval_requests_status ON approval_requests(status);

-- VERIFICATION
SELECT 'Schema audit OK' AS status;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('audit_log', 'approval_requests')
ORDER BY table_name;
