-- Database optimization indices for Data Analytics Dashboard
-- Run this with: psql -d nadia_hitl -f database/migrations/add_analytics_indices.sql

-- Index for common filtering and sorting on interactions table
CREATE INDEX IF NOT EXISTS idx_interactions_created_at_desc ON interactions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_user_id_created_at ON interactions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_date_filtering ON interactions (DATE(created_at));

-- Index for full-text search on messages
CREATE INDEX IF NOT EXISTS idx_interactions_user_message_gin ON interactions USING gin(to_tsvector('english', user_message));
CREATE INDEX IF NOT EXISTS idx_interactions_ai_response_gin ON interactions USING gin(to_tsvector('english', ai_response_formatted));

-- Index for quality and cost analysis
CREATE INDEX IF NOT EXISTS idx_interactions_quality_score ON interactions (quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_interactions_cost_analysis ON interactions (llm1_cost_usd, llm2_cost_usd) WHERE llm1_cost_usd IS NOT NULL OR llm2_cost_usd IS NOT NULL;

-- Index for CTA analysis
CREATE INDEX IF NOT EXISTS idx_interactions_cta_data_gin ON interactions USING gin(cta_data) WHERE cta_data IS NOT NULL;

-- Composite index for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_interactions_dashboard_queries ON interactions (created_at DESC, user_id, quality_score) WHERE created_at >= NOW() - INTERVAL '30 days';

-- Index for hourly activity analysis
CREATE INDEX IF NOT EXISTS idx_interactions_hourly_analysis ON interactions (EXTRACT(HOUR FROM created_at), DATE(created_at));

-- Index for model tracking and cost optimization
CREATE INDEX IF NOT EXISTS idx_interactions_model_tracking ON interactions (llm1_model, llm2_model, created_at) WHERE llm1_model IS NOT NULL OR llm2_model IS NOT NULL;

-- Customer status table indices
CREATE INDEX IF NOT EXISTS idx_customer_status_user_id ON customer_status (user_id);
CREATE INDEX IF NOT EXISTS idx_customer_status_status ON customer_status (status);
CREATE INDEX IF NOT EXISTS idx_customer_status_ltv ON customer_status (ltv_usd) WHERE ltv_usd > 0;

-- Customer status transitions indices
CREATE INDEX IF NOT EXISTS idx_customer_status_transitions_user_id ON customer_status_transitions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_status_transitions_status_flow ON customer_status_transitions (previous_status, new_status);

-- Performance optimization: partial indices for active data
CREATE INDEX IF NOT EXISTS idx_interactions_recent_active ON interactions (id, created_at, user_id) 
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Index for export operations with date filtering
CREATE INDEX IF NOT EXISTS idx_interactions_export_dates ON interactions (created_at, id) 
WHERE created_at >= '2024-01-01';

-- Analytics aggregation optimization
CREATE INDEX IF NOT EXISTS idx_interactions_daily_metrics ON interactions (DATE(created_at), user_id, llm1_cost_usd, llm2_cost_usd);

-- Backup and cleanup optimization
CREATE INDEX IF NOT EXISTS idx_interactions_cleanup_test_data ON interactions (id, created_at) 
WHERE user_message ILIKE '%test%' OR ai_response_formatted ILIKE '%test%';

-- Statistics update for query planner
ANALYZE interactions;
ANALYZE customer_status;
ANALYZE customer_status_transitions;

-- Create a materialized view for dashboard metrics (optional, for high-volume systems)
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_daily_metrics AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as message_count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(quality_score) as avg_quality,
    SUM(COALESCE(llm1_cost_usd, 0) + COALESCE(llm2_cost_usd, 0)) as daily_cost,
    COUNT(*) FILTER (WHERE cta_data IS NOT NULL) as cta_messages,
    COUNT(*) FILTER (WHERE quality_score >= 4) as high_quality_messages
FROM interactions 
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Index on the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_daily_metrics_date ON dashboard_daily_metrics (date);

-- Refresh function for the materialized view
CREATE OR REPLACE FUNCTION refresh_dashboard_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_daily_metrics;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON dashboard_daily_metrics TO postgres;
GRANT EXECUTE ON FUNCTION refresh_dashboard_metrics() TO postgres;

-- Comments for documentation
COMMENT ON INDEX idx_interactions_created_at_desc IS 'Primary sorting index for dashboard queries';
COMMENT ON INDEX idx_interactions_user_message_gin IS 'Full-text search index for user messages';
COMMENT ON INDEX idx_interactions_dashboard_queries IS 'Composite index for common dashboard filter combinations';
COMMENT ON MATERIALIZED VIEW dashboard_daily_metrics IS 'Pre-aggregated daily metrics for dashboard performance';

-- Print completion message
DO $$
BEGIN
    RAISE NOTICE 'Analytics indices created successfully. Run REFRESH MATERIALIZED VIEW dashboard_daily_metrics; periodically to update metrics.';
END $$;