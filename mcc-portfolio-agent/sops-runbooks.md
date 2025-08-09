# MCC Portfolio Intelligence - Standard Operating Procedures & Runbooks

## Table of Contents
1. [Daily Operations](#daily-operations)
2. [Data Ingestion SOPs](#data-ingestion-sops)
3. [Failure Runbooks](#failure-runbooks)
4. [Communication Templates](#communication-templates)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Emergency Procedures](#emergency-procedures)

---

## Daily Operations

### Morning Checklist (9:00 AM CT)
1. **Check Ingestion Dashboard**
   - [ ] Review overnight email processing status
   - [ ] Check for failed ingestions in log
   - [ ] Verify all Tally form submissions processed
   - [ ] Review reconciliation reports

2. **Data Quality Check**
   ```sql
   -- Run daily data quality check
   SELECT * FROM portfolio.v_company_snapshot 
   WHERE days_since_update > 90 
   ORDER BY days_since_update DESC;
   ```

3. **Review Alerts**
   - Check Finance@markcubancompanies.com for bounce-backs
   - Review Slack #portfolio-updates for notifications
   - Check Azure Function logs for errors

### Weekly Tasks (Mondays)
1. **Send Update Reminders**
   - Email companies missing updates > 60 days
   - Follow up on incomplete Tally forms
   
2. **Data Reconciliation**
   - Run ownership sum validation
   - Check for duplicate cashflows
   - Verify investment/distribution balances

3. **Generate Reports**
   - Portfolio performance summary
   - New investments this week
   - Upcoming board meetings

---

## Data Ingestion SOPs

### SOP-001: Processing Founder Update Emails

**Purpose**: Ensure consistent processing of portfolio company updates

**Trigger**: Email received at Finance@markcubancompanies.com

**Steps**:
1. **Auto-Classification** (Automated)
   - System checks subject for tags: [UPDATE], [FINANCIALS], [BOARD]
   - Matches sender domain to company_id
   
2. **Manual Review** (If auto-classification fails)
   - Open unmatched emails in shared mailbox
   - Identify company using:
     - Sender domain
     - Email signature
     - Content mentions
   - Forward with correct tag: `[UPDATE] Company Name - Period`

3. **Validation**
   - Check extraction confidence in ingestion_log
   - If confidence < 0.7:
     - Review extracted data in database
     - Compare with email content
     - Manually correct if needed

4. **Filing**
   - Ensure email saved to SharePoint: `/Portfolio/{company_id}/Email-Exports/`
   - Attachments saved to appropriate folder

**Email Template for Founders**:
```
Subject: MCC Portfolio Update - [Month Year]

Hi [Founder Name],

Please share your monthly update by replying to this email with:

1. Key Metrics:
   - ARR/Revenue
   - Cash balance & runway
   - Headcount
   - Key KPIs for your business

2. Highlights from the month

3. Challenges you're facing

4. How MCC can help

Alternatively, use our form: https://tally.so/r/mRy1pl

Best,
MCC Portfolio Team
```

### SOP-002: Tally Form Processing

**Purpose**: Process structured updates via Tally forms

**Frequency**: Continuous (webhook-triggered)

**Steps**:
1. **Form Submission** (Founder)
   - Complete form at https://tally.so/r/mRy1pl (Updates)
   - Or https://tally.so/r/wdeeRr (Financials)

2. **Make.com Processing** (Automated)
   - Webhook receives form data
   - Transforms to canonical format
   - Appends to Google Sheet
   - Calls ingestion API

3. **Verification** (Team)
   - Check Google Sheet for new rows
   - Verify "Processed" status
   - If failed, check Make.com logs

4. **Follow-up** (If needed)
   - Contact founder for clarification
   - Update record manually if needed

### SOP-003: CSV Import from Legal Team

**Purpose**: Import historical/bulk data from legal spreadsheets

**Frequency**: Monthly or as needed

**Steps**:
1. **Receive File**
   - Legal team uploads to OneDrive: `/Legal/Portfolio Data/`
   - Or emails to Finance@markcubancompanies.com

2. **Run Parser**
   ```bash
   python csv-parser-backfill.py \
     "/path/to/file.xlsx" \
     --reconciliation-output "recon_$(date +%Y%m%d).csv"
   ```

3. **Review Reconciliation**
   - Open reconciliation report
   - Address issues:
     - Company not found → Create company record
     - Invalid amounts → Check with legal team
     - Future dates → Correct date entry

4. **Approve & Import**
   ```bash
   python csv-parser-backfill.py \
     "/path/to/file.xlsx" \
     --db-connection "$POSTGRES_CONNECTION_STRING"
   ```

5. **Verification**
   - Run data quality queries
   - Spot-check imported records
   - Send confirmation to legal team

### SOP-004: Notebook LM Summary Processing

**Purpose**: Extract insights from AI-processed conversation summaries

**Trigger**: Email with [NOTEBOOKLM] tag

**Steps**:
1. **Forward Summary**
   - Add [NOTEBOOKLM] to subject
   - Include company name in subject
   - Forward to Finance@markcubancompanies.com

2. **Processing** (Automated)
   - System extracts decisions, KPIs, commitments
   - Lower confidence (0.7) applied
   - Stored as comm record

3. **Review** (Weekly)
   - Query Notebook LM summaries:
   ```sql
   SELECT * FROM portfolio.comm 
   WHERE source = 'notebook_lm' 
   AND occurred_at > CURRENT_DATE - INTERVAL '7 days';
   ```

---

## Failure Runbooks

### RB-001: Email Ingestion Failure

**Symptoms**:
- Emails in inbox but not in database
- Azure Function errors in logs

**Investigation**:
```bash
# Check Azure Function logs
az functionapp logs tail --name mcc-portfolio-ingestion --resource-group MCC-Portfolio

# Check Graph API subscription
curl -H "Authorization: Bearer $TOKEN" \
  "https://graph.microsoft.com/v1.0/subscriptions"
```

**Resolution Steps**:
1. **Check Authentication**
   - Verify Graph API token not expired
   - Refresh app registration if needed
   
2. **Reprocess Failed Messages**
   ```python
   # Manual reprocessing script
   python reprocess_emails.py --from "2025-01-15" --to "2025-01-16"
   ```

3. **If Extraction Fails**
   - Check company_id mapping
   - Verify extraction patterns
   - Manually enter data if critical

### RB-002: Make.com Scenario Failure

**Symptoms**:
- Tally submissions not appearing in sheet
- API calls failing

**Investigation**:
- Check Make.com dashboard for errors
- Review scenario execution history
- Verify webhook is active

**Resolution**:
1. **Restart Scenario**
   - Pause scenario
   - Clear error queue
   - Resume scenario

2. **Replay Failed Executions**
   - Go to History tab
   - Select failed executions
   - Click "Replay"

3. **Manual Processing**
   - Export Tally responses as CSV
   - Use CSV parser to import

### RB-003: Database Connection Issues

**Symptoms**:
- "Connection refused" errors
- Slow queries or timeouts

**Investigation**:
```sql
-- Check active connections
SELECT pid, usename, application_name, state 
FROM pg_stat_activity;

-- Check database size
SELECT pg_database_size('portfolio')/1024/1024 as size_mb;
```

**Resolution**:
1. **Connection Pool Exhaustion**
   ```sql
   -- Terminate idle connections
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND state_change < NOW() - INTERVAL '10 minutes';
   ```

2. **Performance Issues**
   - Run VACUUM ANALYZE
   - Check index usage
   - Scale database if needed

### RB-004: Data Quality Issues

**Symptoms**:
- Ownership > 100%
- Negative runway
- Duplicate records

**Investigation**:
```sql
-- Find data anomalies
SELECT company_id, SUM(fully_diluted_pct) as total_ownership
FROM portfolio.ownership o1
WHERE as_of_date = (
  SELECT MAX(as_of_date) FROM portfolio.ownership o2 
  WHERE o2.company_id = o1.company_id
)
GROUP BY company_id
HAVING SUM(fully_diluted_pct) > 100;
```

**Resolution**:
1. **Identify Source**
   - Check source_ptr for bad data
   - Review extraction confidence
   
2. **Correct Data**
   ```sql
   -- Update with correct values
   UPDATE portfolio.ownership 
   SET fully_diluted_pct = [correct_value],
       notes = 'Manual correction: ' || notes
   WHERE ownership_id = '[id]';
   ```

3. **Prevent Recurrence**
   - Update extraction patterns
   - Add validation rules
   - Train team on correct data entry

---

## Communication Templates

### Template: Missing Update Reminder
```
Subject: MCC Portfolio - Update Request for [Company Name]

Hi [Founder Name],

We noticed we haven't received your recent update. Please take 5 minutes to share your progress:

Quick Form: https://tally.so/r/mRy1pl
Or reply to this email with your update.

If you're facing challenges, we're here to help.

Best,
MCC Portfolio Team
```

### Template: Data Discrepancy
```
Subject: MCC Portfolio - Quick Data Verification Needed

Hi [Founder Name],

We're updating our records and need to verify:
- Current ownership: [X]%
- Last investment amount: $[Y]
- Current status: [Active/Other]

Could you confirm these are correct?

Thanks,
MCC Portfolio Team
```

### Template: Successful Processing
```
Subject: ✅ Update Received - [Company Name] [Period]

Thanks for your update! We've processed your [Month] report.

Recorded metrics:
- ARR: $[X]
- Runway: [Y] months
- [Other key metrics]

Your next update is due: [Date]

Best,
MCC Portfolio Team
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

**Real-time (< 5 min)**
- Email ingestion queue depth
- API endpoint availability
- Database connection pool

**Hourly**
- Failed ingestion count
- Extraction confidence distribution
- New records created

**Daily**
- Companies missing updates
- Data quality scores
- Storage usage

### Alert Configuration

```yaml
# Azure Monitor Alert Rules
alerts:
  - name: "Ingestion Failure Rate High"
    condition: "failure_rate > 10%"
    window: "5 minutes"
    action: "Email + Slack"
    
  - name: "No Updates Received"
    condition: "update_count == 0"
    window: "24 hours"
    action: "Email team"
    
  - name: "Low Confidence Extractions"
    condition: "avg(confidence) < 0.6"
    window: "1 hour"
    action: "Review queue"
```

### Dashboards

**Operations Dashboard**
- Ingestion success rate (24h)
- Average processing time
- Queue depth
- Error breakdown by type

**Portfolio Health Dashboard**
- Companies by update recency
- Data completeness scores
- Investment/distribution totals
- Ownership verification status

---

## Emergency Procedures

### EP-001: Complete System Outage

**Priority**: P0 - Critical

**Steps**:
1. **Immediate**
   - Notify team via Slack/phone
   - Check Azure service health
   - Switch to manual processing

2. **Communication**
   - Email founders about delay
   - Set up temporary Google Form

3. **Recovery**
   - Queue all pending items
   - Process backlog gradually
   - Verify no data loss

### EP-002: Data Breach/Security Incident

**Priority**: P0 - Critical

**Steps**:
1. **Contain**
   - Disable affected accounts
   - Rotate credentials
   - Isolate affected systems

2. **Assess**
   - Identify exposed data
   - Determine timeline
   - Check access logs

3. **Notify**
   - Legal team immediately
   - Affected companies within 24h
   - Compliance officer

### EP-003: Bulk Data Corruption

**Priority**: P1 - High

**Steps**:
1. **Stop Processing**
   - Pause all ingestion
   - Prevent cascade corruption

2. **Identify Scope**
   ```sql
   -- Find affected records
   SELECT COUNT(*), MIN(updated_at), MAX(updated_at)
   FROM portfolio.[affected_table]
   WHERE [corruption_condition];
   ```

3. **Restore**
   - From backup if available
   - From source documents
   - Manual correction if needed

---

## Appendix: Quick Reference

### Common SQL Queries
```sql
-- Companies needing updates
SELECT company_id, legal_name, days_since_update
FROM portfolio.v_company_snapshot
WHERE status = 'active' AND days_since_update > 30
ORDER BY days_since_update DESC;

-- Recent high-value investments
SELECT c.legal_name, cf.date, cf.amount
FROM portfolio.cashflow cf
JOIN portfolio.company c ON cf.company_id = c.company_id
WHERE cf.kind = 'Investment' 
  AND cf.date > CURRENT_DATE - INTERVAL '30 days'
  AND cf.amount > 1000000
ORDER BY cf.date DESC;

-- Data quality check
SELECT 
  COUNT(DISTINCT company_id) as total_companies,
  COUNT(CASE WHEN latest_update > CURRENT_DATE - 90 THEN 1 END) as updated_companies,
  AVG(confidence_overall) as avg_confidence
FROM portfolio.company c
LEFT JOIN portfolio.update u ON c.company_id = u.company_id;
```

### Key Contacts
- **Technical Issues**: devops@markcubancompanies.com
- **Legal Questions**: legal@markcubancompanies.com  
- **Azure Support**: [Support ticket portal]
- **Make.com Support**: support@make.com

### Useful Links
- [Azure Portal](https://portal.azure.com)
- [Make.com Dashboard](https://www.make.com/en/login)
- [SharePoint Site](https://markcubancompanies.sharepoint.com/sites/Portfolio)
- [Tally Forms Admin](https://tally.so/forms)
- [Master Google Sheet](https://docs.google.com/spreadsheets/d/1ZUlnPeNTOYmYKj93ozmY0pJZeLGfFrdKwW-OYKNjkyc)

---

*Last Updated: 2025-08-08*
*Version: 1.0*
*Owner: MCC Portfolio Intelligence Team*