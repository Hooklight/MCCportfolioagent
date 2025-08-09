-- MCC Portfolio Intelligence Database Schema
-- PostgreSQL DDL for canonical data model
-- Version: 1.0.0
-- Created: 2025-08-08

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy company name matching

-- Create schema
CREATE SCHEMA IF NOT EXISTS portfolio;
SET search_path TO portfolio, public;

-- Company table (core entity)
CREATE TABLE company (
    company_id VARCHAR(100) PRIMARY KEY, -- lowercase-kebab slug
    legal_name VARCHAR(255) NOT NULL,
    aka VARCHAR(255),
    website VARCHAR(500),
    status VARCHAR(50) CHECK (status IN ('active', 'inactive', 'exited', 'written_off')),
    earliest_close_date DATE,
    hq_city VARCHAR(100),
    hq_state VARCHAR(50),
    notes TEXT,
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Round table (investment rounds)
CREATE TABLE round (
    round_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL REFERENCES company(company_id),
    type VARCHAR(50) CHECK (type IN ('Seed', 'A', 'B', 'Bridge', 'Note', 'SAFE', 'Secondary', 'Other')),
    close_date DATE,
    pre_money DECIMAL(18,2),
    post_money DECIMAL(18,2),
    amount_invested_by_mcc DECIMAL(18,2),
    instrument VARCHAR(50) CHECK (instrument IN ('Equity', 'SAFE', 'Convertible Note', 'Royalty', 'Other')),
    lead_investor VARCHAR(255),
    source_doc_id VARCHAR(255),
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Constraints
    CONSTRAINT check_money_values CHECK (
        (pre_money IS NULL OR pre_money >= 0) AND
        (post_money IS NULL OR post_money >= 0) AND
        (amount_invested_by_mcc IS NULL OR amount_invested_by_mcc >= 0)
    )
);

-- Ownership table (equity positions over time)
CREATE TABLE ownership (
    ownership_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL REFERENCES company(company_id),
    as_of_date DATE NOT NULL,
    security_class VARCHAR(100),
    shares_or_units DECIMAL(18,4),
    fully_diluted_pct DECIMAL(5,2) CHECK (fully_diluted_pct BETWEEN 0 AND 100),
    notes TEXT,
    source_doc_id VARCHAR(255),
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Ensure no duplicate ownership records for same company/date
    UNIQUE(company_id, as_of_date, security_class)
);

-- Cashflow table (all money movements)
CREATE TABLE cashflow (
    cashflow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL REFERENCES company(company_id),
    date DATE NOT NULL,
    kind VARCHAR(50) CHECK (kind IN ('Investment', 'Distribution', 'Dividend', 'Royalty', 'Expense_Reimburse', 'Other')),
    instrument VARCHAR(100),
    amount DECIMAL(18,2) NOT NULL,
    wire_ref VARCHAR(100),
    notes TEXT,
    source_doc_id VARCHAR(255),
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Prevent duplicate cashflows
    UNIQUE(company_id, date, amount, wire_ref)
);

-- Update table (periodic company updates)
CREATE TABLE update (
    update_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL REFERENCES company(company_id),
    period_start DATE,
    period_end DATE,
    report_period VARCHAR(20), -- e.g., '2025-Q2'
    metrics JSONB, -- Flexible KPI storage (ARR, revenue, GM, CAC, LTV, cash, runway, headcount, churn)
    qualitative_summary TEXT,
    update_deck_doc_id VARCHAR(255),
    email_msg_id VARCHAR(255),
    confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0 AND 1),
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Contact table
CREATE TABLE contact (
    contact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) NOT NULL REFERENCES company(company_id),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    is_primary BOOLEAN DEFAULT FALSE,
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document table (file references)
CREATE TABLE document (
    doc_id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(100) REFERENCES company(company_id),
    storage_url TEXT NOT NULL,
    title VARCHAR(500),
    doc_type VARCHAR(50),
    checksum VARCHAR(64),
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acl TEXT, -- JSON array of permission groups
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Communication table (emails, calls, notebook_lm)
CREATE TABLE comm (
    comm_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id VARCHAR(100) REFERENCES company(company_id),
    source VARCHAR(50) CHECK (source IN ('email', 'notebook_lm', 'sms', 'call')),
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    participants TEXT[], -- Array of email addresses or names
    summary TEXT,
    extracted_fields JSONB,
    raw_ptr TEXT, -- Pointer to raw message/file
    -- Lineage fields
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    source_url TEXT,
    extractor_version VARCHAR(20),
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Ingestion log for audit trail
CREATE TABLE ingestion_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingestion_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    source_type VARCHAR(50),
    source_id VARCHAR(255),
    company_id VARCHAR(100),
    records_created JSONB, -- {"company": 1, "rounds": 2, "cashflows": 3}
    confidence_scores JSONB,
    anomalies TEXT[],
    assumptions TEXT[],
    processing_time_ms INTEGER,
    status VARCHAR(20) CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT
);

-- Create indexes for performance
CREATE INDEX idx_company_status ON company(status);
CREATE INDEX idx_company_legal_name_trgm ON company USING gin(legal_name gin_trgm_ops);
CREATE INDEX idx_round_company_date ON round(company_id, close_date DESC);
CREATE INDEX idx_ownership_company_date ON ownership(company_id, as_of_date DESC);
CREATE INDEX idx_cashflow_company_date ON cashflow(company_id, date DESC);
CREATE INDEX idx_update_company_period ON update(company_id, period_end DESC);
CREATE INDEX idx_contact_company_primary ON contact(company_id, is_primary);
CREATE INDEX idx_document_company ON document(company_id);
CREATE INDEX idx_comm_company_occurred ON comm(company_id, occurred_at DESC);
CREATE INDEX idx_update_metrics ON update USING gin(metrics);

-- Create views for common queries
CREATE OR REPLACE VIEW v_company_snapshot AS
SELECT 
    c.company_id,
    c.legal_name,
    c.status,
    c.website,
    c.hq_city,
    c.hq_state,
    -- Latest ownership
    COALESCE(o.fully_diluted_pct, 0) as current_ownership_pct,
    o.as_of_date as ownership_as_of,
    -- Total invested
    COALESCE(SUM(cf_inv.amount), 0) as total_invested,
    -- Total distributions
    COALESCE(SUM(cf_dist.amount), 0) as total_distributed,
    -- Net position
    COALESCE(SUM(cf_dist.amount), 0) - COALESCE(SUM(cf_inv.amount), 0) as net_position,
    -- Latest update
    u.period_end as last_update_date,
    u.metrics->>'ARR' as latest_arr,
    u.metrics->>'revenue' as latest_revenue,
    u.metrics->>'runway_months' as runway_months,
    -- Days since last update
    EXTRACT(DAY FROM CURRENT_DATE - u.period_end) as days_since_update
FROM company c
LEFT JOIN LATERAL (
    SELECT fully_diluted_pct, as_of_date 
    FROM ownership 
    WHERE company_id = c.company_id 
    ORDER BY as_of_date DESC 
    LIMIT 1
) o ON TRUE
LEFT JOIN LATERAL (
    SELECT period_end, metrics 
    FROM update 
    WHERE company_id = c.company_id 
    ORDER BY period_end DESC 
    LIMIT 1
) u ON TRUE
LEFT JOIN cashflow cf_inv ON cf_inv.company_id = c.company_id AND cf_inv.kind = 'Investment'
LEFT JOIN cashflow cf_dist ON cf_dist.company_id = c.company_id AND cf_dist.kind IN ('Distribution', 'Dividend')
GROUP BY c.company_id, c.legal_name, c.status, c.website, c.hq_city, c.hq_state,
         o.fully_diluted_pct, o.as_of_date, u.period_end, u.metrics;

-- Cumulative cashflow view
CREATE OR REPLACE VIEW v_cashflow_cumulative AS
SELECT 
    company_id,
    date,
    kind,
    amount,
    SUM(CASE WHEN kind = 'Investment' THEN -amount ELSE amount END) 
        OVER (PARTITION BY company_id ORDER BY date, cashflow_id) as cumulative_position,
    SUM(amount) OVER (PARTITION BY company_id, kind ORDER BY date, cashflow_id) as cumulative_by_type
FROM cashflow
ORDER BY company_id, date;

-- Update triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_company_updated_at BEFORE UPDATE ON company FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_round_updated_at BEFORE UPDATE ON round FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ownership_updated_at BEFORE UPDATE ON ownership FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_cashflow_updated_at BEFORE UPDATE ON cashflow FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_update_updated_at BEFORE UPDATE ON update FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contact_updated_at BEFORE UPDATE ON contact FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_updated_at BEFORE UPDATE ON document FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_comm_updated_at BEFORE UPDATE ON comm FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant appropriate permissions (adjust as needed)
GRANT SELECT ON ALL TABLES IN SCHEMA portfolio TO readonly_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA portfolio TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA portfolio TO app_user;