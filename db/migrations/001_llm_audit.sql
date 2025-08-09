-- LLM Audit Logging Schema
-- Migration 001: Create audit log table for LLM interactions

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS audit;

-- Create main audit log table
CREATE TABLE IF NOT EXISTS audit.llm_audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    prompt_hash TEXT NOT NULL,
    response_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms INTEGER CHECK (latency_ms >= 0),
    user_id TEXT,
    meta JSONB DEFAULT '{}',
    
    -- Additional audit fields
    request_id UUID DEFAULT gen_random_uuid(),
    session_id TEXT,
    ip_address INET,
    user_agent TEXT,
    
    -- Security and compliance fields
    contains_pii BOOLEAN DEFAULT FALSE,
    flagged_content BOOLEAN DEFAULT FALSE,
    moderation_score NUMERIC(3,2) CHECK (moderation_score >= 0 AND moderation_score <= 1),
    
    -- Token usage tracking
    prompt_tokens INTEGER CHECK (prompt_tokens >= 0),
    completion_tokens INTEGER CHECK (completion_tokens >= 0),
    total_tokens INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    
    -- Cost tracking
    estimated_cost_usd NUMERIC(10,6) CHECK (estimated_cost_usd >= 0),
    
    -- Response metadata
    temperature NUMERIC(3,2) CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER CHECK (max_tokens > 0),
    top_p NUMERIC(3,2) CHECK (top_p >= 0 AND top_p <= 1),
    
    -- Status and error tracking
    status TEXT CHECK (status IN ('success', 'error', 'timeout', 'rate_limited', 'cancelled')),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 CHECK (retry_count >= 0)
);

-- Create indexes for common queries
CREATE INDEX idx_llm_audit_ts ON audit.llm_audit_log(ts DESC);
CREATE INDEX idx_llm_audit_user_id ON audit.llm_audit_log(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_llm_audit_model ON audit.llm_audit_log(model);
CREATE INDEX idx_llm_audit_session_id ON audit.llm_audit_log(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_llm_audit_request_id ON audit.llm_audit_log(request_id);
CREATE INDEX idx_llm_audit_status ON audit.llm_audit_log(status);
CREATE INDEX idx_llm_audit_flagged ON audit.llm_audit_log(flagged_content) WHERE flagged_content = TRUE;
CREATE INDEX idx_llm_audit_meta ON audit.llm_audit_log USING GIN(meta);

-- Create summary statistics view
CREATE VIEW audit.llm_audit_summary AS
SELECT 
    DATE_TRUNC('hour', ts) as hour,
    model,
    COUNT(*) as request_count,
    AVG(latency_ms) as avg_latency_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as median_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms,
    SUM(total_tokens) as total_tokens_used,
    SUM(estimated_cost_usd) as total_cost_usd,
    COUNT(DISTINCT user_id) as unique_users,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
    AVG(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::NUMERIC(5,4) as success_rate
FROM audit.llm_audit_log
GROUP BY DATE_TRUNC('hour', ts), model;

-- Create daily aggregation table for performance
CREATE TABLE IF NOT EXISTS audit.llm_audit_daily (
    date DATE NOT NULL,
    model TEXT NOT NULL,
    request_count BIGINT NOT NULL DEFAULT 0,
    unique_users INTEGER NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC(12,6) DEFAULT 0,
    avg_latency_ms NUMERIC(10,2),
    error_count INTEGER NOT NULL DEFAULT 0,
    flagged_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, model)
);

-- Function to partition by month for large-scale deployments
CREATE OR REPLACE FUNCTION audit.create_monthly_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_date := DATE_TRUNC('month', CURRENT_DATE);
    partition_name := 'llm_audit_log_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := partition_date;
    end_date := partition_date + INTERVAL '1 month';
    
    -- Check if partition already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_class 
        WHERE relname = partition_name 
        AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'audit')
    ) THEN
        EXECUTE format(
            'CREATE TABLE audit.%I PARTITION OF audit.llm_audit_log 
            FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        
        RAISE NOTICE 'Created partition: %', partition_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Grant appropriate permissions
GRANT USAGE ON SCHEMA audit TO llm_app_user;
GRANT INSERT, SELECT ON audit.llm_audit_log TO llm_app_user;
GRANT SELECT ON audit.llm_audit_summary TO llm_app_user;
GRANT SELECT ON audit.llm_audit_daily TO llm_app_user;

-- Add comment for documentation
COMMENT ON TABLE audit.llm_audit_log IS 'Audit log for all LLM API interactions including prompts, responses, and metadata';
COMMENT ON COLUMN audit.llm_audit_log.prompt_hash IS 'SHA-256 hash of the prompt for privacy-preserving audit';
COMMENT ON COLUMN audit.llm_audit_log.response_hash IS 'SHA-256 hash of the response for privacy-preserving audit';
COMMENT ON COLUMN audit.llm_audit_log.meta IS 'Additional metadata as JSONB for flexible schema extension';