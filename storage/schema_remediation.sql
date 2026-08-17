-- ============================================================
-- Schema PostgreSQL - Remediation Agent
-- ============================================================

DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS problem_actions CASCADE;
DROP TABLE IF EXISTS actions CASCADE;
DROP TABLE IF EXISTS problems CASCADE;

-- ============================================================
-- PROBLEMS
-- ============================================================

CREATE TABLE problems (
    problem_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    condition TEXT NOT NULL,
    affected_component TEXT NOT NULL,
    duration_s INTEGER DEFAULT 0,
    known_causes JSONB DEFAULT '[]',
    severity_default TEXT NOT NULL
        CHECK (severity_default IN ('low','medium','high','critical')),
    tags JSONB DEFAULT '[]',
    occurrences INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- ACTIONS
-- ============================================================

CREATE TABLE actions (
    action_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    executor TEXT NOT NULL,
    params_schema JSONB DEFAULT '{}',
    risk_level TEXT NOT NULL
        CHECK (risk_level IN ('low','medium','high')),
    reversible BOOLEAN NOT NULL DEFAULT true,
    avg_resolution_time_s INTEGER DEFAULT 0,
    success_rate_historical NUMERIC(4,3) DEFAULT 0.5,
    executions_count INTEGER DEFAULT 0,
    successes_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- RELATION PROBLEM -> ACTION
-- ============================================================

CREATE TABLE problem_actions (
    problem_id TEXT REFERENCES problems(problem_id) ON DELETE CASCADE,
    action_id TEXT NOT NULL REFERENCES actions(action_id) ON DELETE CASCADE,
    PRIMARY KEY (problem_id, action_id)
);

-- ============================================================
-- DECISIONS
-- ============================================================

CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    anomaly_id TEXT NOT NULL,
    matched_problem_id TEXT REFERENCES problems(problem_id),
    candidate_actions JSONB NOT NULL DEFAULT '[]',
    chosen_action_id TEXT,
    decision_mode TEXT NOT NULL
        CHECK (decision_mode IN (
            'AUTO_EXECUTE',
            'SUGGEST_TO_HUMAN',
            'ESCALATE'
        )),
    confidence NUMERIC(4,3),
    reason TEXT,
    execution_status TEXT
        CHECK (execution_status IN (
            'pending',
            'success',
            'failed',
            'skipped',
            'overridden'
        )),
    resolution_time_s INTEGER,
    human_override BOOLEAN DEFAULT false,
    feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

-- ============================================================
-- INDEX
-- ============================================================

CREATE INDEX idx_decisions_anomaly
    ON decisions(anomaly_id);

CREATE INDEX idx_decisions_created_at
    ON decisions(created_at DESC);

CREATE INDEX idx_problems_metric_component
    ON problems(metric, affected_component);

-- ============================================================
-- VERIFICATION
-- ============================================================

SELECT 'Schema remediation OK' AS status;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'problems',
      'actions',
      'problem_actions',
      'decisions'
  )
ORDER BY table_name;