# MCC Portfolio Intelligence - Deployment Checklist & Configuration Guide

## Pre-Deployment Requirements

### Azure Resources Required
- [ ] Azure Subscription with appropriate permissions
- [ ] Resource Group: `rg-mcc-portfolio-prod`
- [ ] Azure Database for PostgreSQL (Flexible Server)
- [ ] Azure Function App (Consumption or Premium plan)
- [ ] Azure Storage Account for artifacts
- [ ] Azure Key Vault for secrets
- [ ] Application Insights for monitoring

### Microsoft 365 Requirements
- [ ] Admin access to M365 tenant
- [ ] SharePoint site created: `/sites/Portfolio`
- [ ] Shared mailbox: `Finance@markcubancompanies.com`
- [ ] Graph API permissions configured

### Third-Party Services
- [ ] Make.com account (Team plan or higher)
- [ ] Tally forms account with API access
- [ ] Google Workspace for sheets access

---

## Phase 1: Infrastructure Setup (Day 1)

### 1.1 PostgreSQL Database
```bash
# Create PostgreSQL server
az postgres flexible-server create \
  --resource-group rg-mcc-portfolio-prod \
  --name mcc-portfolio-db \
  --location eastus \
  --tier Burstable \
  --sku-name B1ms \
  --storage-size 32 \
  --version 14 \
  --admin-user mccadmin \
  --admin-password [SECURE_PASSWORD]

# Configure firewall
az postgres flexible-server firewall-rule create \
  --resource-group rg-mcc-portfolio-prod \
  --name mcc-portfolio-db \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Create database
az postgres flexible-server db create \
  --resource-group rg-mcc-portfolio-prod \
  --server-name mcc-portfolio-db \
  --database-name portfolio
```

- [ ] Database server created
- [ ] Firewall rules configured
- [ ] Connection string saved to Key Vault
- [ ] Run schema DDL script: `psql -f mcc-portfolio-schema.sql`
- [ ] Create read-only user for reporting
- [ ] Configure backup retention (7 days minimum)

### 1.2 Azure Function App
```bash
# Create Function App
az functionapp create \
  --resource-group rg-mcc-portfolio-prod \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name mcc-portfolio-ingestion \
  --storage-account mccportfoliostorage \
  --os-type Linux

# Configure app settings
az functionapp config appsettings set \
  --name mcc-portfolio-ingestion \
  --resource-group rg-mcc-portfolio-prod \
  --settings \
    "AZURE_TENANT_ID=[TENANT_ID]" \
    "AZURE_CLIENT_ID=[CLIENT_ID]" \
    "POSTGRES_CONNECTION_STRING=@Microsoft.KeyVault(SecretUri=https://mcc-keyvault.vault.azure.net/secrets/db-connection)" \
    "SHAREPOINT_SITE_URL=https://markcubancompanies.sharepoint.com/sites/Portfolio"
```

- [ ] Function App created
- [ ] Python 3.9 runtime configured
- [ ] Application settings configured
- [ ] Key Vault references enabled
- [ ] Deploy function code: `func azure functionapp publish mcc-portfolio-ingestion`
- [ ] Test function locally first

### 1.3 Storage Account
```bash
# Create storage account
az storage account create \
  --name mccportfoliostorage \
  --resource-group rg-mcc-portfolio-prod \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2

# Create container
az storage container create \
  --name portfolio-artifacts \
  --account-name mccportfoliostorage \
  --public-access off
```

- [ ] Storage account created
- [ ] Container for artifacts created
- [ ] Lifecycle management configured (archive after 90 days)
- [ ] Soft delete enabled

---

## Phase 2: Microsoft 365 Configuration (Day 2)

### 2.1 App Registration for Graph API
1. Navigate to Azure Portal > Azure Active Directory > App registrations
2. New registration:
   - Name: `MCC Portfolio Intelligence`
   - Supported account types: Single tenant
3. Configure API permissions:
   ```
   Microsoft Graph:
   - Mail.Read (Application)
   - Mail.ReadWrite (Application)
   - Files.ReadWrite.All (Application)
   - Sites.ReadWrite.All (Application)
   - User.Read.All (Application)
   ```
4. Create client secret and save to Key Vault

- [ ] App registration created
- [ ] API permissions granted and admin consented
- [ ] Client secret created (expires in 2 years)
- [ ] Service principal created

### 2.2 Graph Webhook Subscription
```python
# Create subscription for email monitoring
subscription = {
    "changeType": "created",
    "notificationUrl": "https://mcc-portfolio-ingestion.azurewebsites.net/api/EmailWebhook",
    "resource": "users/Finance@markcubancompanies.com/messages",
    "expirationDateTime": "2025-02-01T00:00:00.0000000Z",
    "clientState": "SecretClientState"
}
```

- [ ] Webhook endpoint deployed and validated
- [ ] Graph subscription created
- [ ] Subscription renewal automation configured

### 2.3 SharePoint Setup
```powershell
# Run SharePoint setup script
.\sharepoint-setup.ps1 `
  -TenantUrl "https://markcubancompanies.sharepoint.com" `
  -SiteUrl "https://markcubancompanies.sharepoint.com/sites/Portfolio" `
  -AdminEmail "admin@markcubancompanies.com"
```

- [ ] SharePoint site created
- [ ] Folder structure created
- [ ] Security groups configured
- [ ] Metadata columns added
- [ ] Views created
- [ ] Permissions set

---

## Phase 3: Third-Party Integrations (Day 3)

### 3.1 Make.com Configuration
1. Import blueprint: `make-com-blueprint.json`
2. Configure connections:
   - Tally OAuth
   - Google Sheets OAuth
   - Microsoft 365 OAuth
   - Slack OAuth
3. Set variables:
   - `INGESTION_API_URL`: Function App URL
   - `API_KEY`: Generated API key

- [ ] Blueprint imported
- [ ] All connections authorized
- [ ] Webhook URL configured in Tally
- [ ] Test scenario with sample data
- [ ] Schedule activated (15-minute interval)

### 3.2 Tally Forms Setup
1. Configure webhooks for both forms:
   - Company Update: `https://hook.us1.make.com/[webhook_id_1]`
   - Financials: `https://hook.us1.make.com/[webhook_id_2]`
2. Test form submissions

- [ ] Webhooks configured
- [ ] Test submissions successful
- [ ] Response notifications working

### 3.3 Google Sheets
1. Share Master Sheet with service account
2. Configure appropriate permissions
3. Set up backup automation

- [ ] Sheet shared with Make.com
- [ ] Headers configured correctly
- [ ] Backup automation enabled

---

## Phase 4: Data Migration (Day 4)

### 4.1 Historical Data Import
```bash
# Import legal team spreadsheet
python csv-parser-backfill.py \
  "/path/to/historical_data.xlsx" \
  --db-connection "$POSTGRES_CONNECTION_STRING" \
  --reconciliation-output "import_reconciliation.csv"
```

- [ ] Historical data files collected
- [ ] Test import on staging first
- [ ] Review reconciliation report
- [ ] Resolve unmapped companies
- [ ] Production import completed
- [ ] Data validation queries run

### 4.2 Initial Company Setup
```sql
-- Verify all active companies present
SELECT COUNT(*) as company_count,
       COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count
FROM portfolio.company;

-- Check data completeness
SELECT company_id, legal_name
FROM portfolio.company
WHERE company_id NOT IN (
  SELECT DISTINCT company_id FROM portfolio.ownership
);
```

- [ ] All active portfolio companies added
- [ ] Ownership records populated
- [ ] Investment history loaded
- [ ] Contact information added

---

## Phase 5: Testing & Validation (Day 5)

### 5.1 End-to-End Testing
```bash
# Run test suite
python test-suite.py
```

- [ ] Unit tests passing (100%)
- [ ] Integration tests passing
- [ ] Performance benchmarks met
- [ ] Email extraction accuracy > 90%
- [ ] CSV parsing working for all formats

### 5.2 User Acceptance Testing
Test each workflow:

**Email Processing:**
- [ ] Send test UPDATE email → Verify in database
- [ ] Send test FINANCIALS email → Verify extraction
- [ ] Send attachment → Verify SharePoint storage
- [ ] Send unmatched company → Verify handling

**Form Processing:**
- [ ] Submit Tally update form → Verify in sheet and database
- [ ] Submit financial form → Verify processing
- [ ] Test validation errors → Verify handling

**Manual Operations:**
- [ ] Upload CSV → Verify import
- [ ] Run reconciliation → Verify report
- [ ] Query database → Verify views working

### 5.3 Load Testing
- [ ] Process 100 emails in batch
- [ ] Submit 50 form responses rapidly
- [ ] Import 10,000 row CSV
- [ ] Verify no performance degradation

---

## Phase 6: Monitoring & Alerts (Day 6)

### 6.1 Application Insights
```bash
# Enable Application Insights
az monitor app-insights component create \
  --app mcc-portfolio-insights \
  --location eastus \
  --resource-group rg-mcc-portfolio-prod \
  --application-type web

# Link to Function App
az functionapp config appsettings set \
  --name mcc-portfolio-ingestion \
  --resource-group rg-mcc-portfolio-prod \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=[KEY]"
```

- [ ] Application Insights configured
- [ ] Custom metrics defined
- [ ] Dashboards created
- [ ] Log Analytics workspace connected

### 6.2 Alert Rules
Create alerts for:
- [ ] Function execution failures > 5 in 10 minutes
- [ ] Database connection failures
- [ ] Extraction confidence < 60%
- [ ] No emails processed in 24 hours
- [ ] Make.com scenario failures
- [ ] Storage account quota > 80%

### 6.3 Dashboards
- [ ] Operations dashboard in Azure Portal
- [ ] Power BI report for portfolio metrics
- [ ] Slack integration for real-time alerts

---

## Phase 7: Documentation & Training (Day 7)

### 7.1 Documentation
- [ ] Update README with production URLs
- [ ] Document all credentials in Key Vault
- [ ] Create architecture diagram
- [ ] Update runbooks with production details
- [ ] Create troubleshooting guide

### 7.2 Team Training
Conduct training sessions:
- [ ] Finance team: Using the shared mailbox
- [ ] Founders: Submitting updates via email/forms
- [ ] Legal team: CSV export process
- [ ] Ops team: Monitoring and troubleshooting
- [ ] Leadership: Accessing reports

### 7.3 Support Materials
- [ ] Create video walkthrough
- [ ] Prepare FAQ document
- [ ] Set up internal wiki page
- [ ] Create quick reference cards

---

## Go-Live Checklist

### Pre-Launch (T-24 hours)
- [ ] Final backup of any existing data
- [ ] Freeze changes to production
- [ ] Communication sent to all stakeholders
- [ ] Support team on standby

### Launch (T-0)
- [ ] Enable email forwarding rules
- [ ] Activate Make.com scenarios
- [ ] Enable Graph webhooks
- [ ] Start monitoring dashboards
- [ ] Send test transactions

### Post-Launch (T+24 hours)
- [ ] Review first 24 hours of logs
- [ ] Address any critical issues
- [ ] Gather initial feedback
- [ ] Fine-tune extraction rules
- [ ] Schedule follow-up training if needed

---

## Configuration Reference

### Environment Variables
```bash
# Azure
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=**********
AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Database
POSTGRES_CONNECTION_STRING=postgresql://user:pass@host:5432/portfolio?sslmode=require

# SharePoint
SHAREPOINT_SITE_URL=https://markcubancompanies.sharepoint.com/sites/Portfolio
SHAREPOINT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
STORAGE_ACCOUNT_NAME=mccportfoliostorage
STORAGE_CONTAINER=portfolio-artifacts

# Monitoring
APPINSIGHTS_INSTRUMENTATIONKEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# API Keys
MAKE_COM_API_KEY=**********
TALLY_API_KEY=**********
```

### Connection Strings
```json
{
  "Database": {
    "Primary": "postgresql://mccadmin@mcc-portfolio-db:password@mcc-portfolio-db.postgres.database.azure.com:5432/portfolio?sslmode=require",
    "ReadOnly": "postgresql://readonly@mcc-portfolio-db:password@mcc-portfolio-db.postgres.database.azure.com:5432/portfolio?sslmode=require"
  },
  "Storage": {
    "Primary": "DefaultEndpointsProtocol=https;AccountName=mccportfoliostorage;AccountKey=...;EndpointSuffix=core.windows.net"
  },
  "ServiceBus": {
    "Ingestion": "Endpoint=sb://mcc-portfolio.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=..."
  }
}
```

### API Endpoints
```
Production:
- Ingestion API: https://mcc-portfolio-ingestion.azurewebsites.net/api/
- Email Webhook: https://mcc-portfolio-ingestion.azurewebsites.net/api/EmailWebhook
- Update Endpoint: https://mcc-portfolio-ingestion.azurewebsites.net/api/ingest/update

Staging:
- Ingestion API: https://mcc-portfolio-staging.azurewebsites.net/api/
```

---

## Rollback Plan

If critical issues arise:

1. **Immediate Actions:**
   - Disable Graph webhooks
   - Pause Make.com scenarios
   - Stop Function App
   - Redirect emails to manual processing

2. **Data Rollback:**
   ```sql
   -- Restore from backup
   pg_restore -d portfolio portfolio_backup_[timestamp].sql
   
   -- Or delete recent ingestions
   DELETE FROM portfolio.ingestion_log 
   WHERE ingestion_timestamp > '[go_live_time]';
   ```

3. **Communication:**
   - Notify all stakeholders
   - Provide alternative submission methods
   - Schedule post-mortem

---

## Success Metrics (30 days post-launch)

- [ ] 95% of emails processed automatically
- [ ] < 5% extraction error rate  
- [ ] 100% of active companies with current data
- [ ] < 2 minute average processing time
- [ ] Zero data loss incidents
- [ ] 90% user satisfaction score

---

## Contacts

**Technical Support:**
- Infrastructure: devops@markcubancompanies.com
- Database: dataeng@markcubancompanies.com
- Application: dev@markcubancompanies.com

**Business Contacts:**
- Portfolio Team: portfolio@markcubancompanies.com
- Finance Team: finance@markcubancompanies.com
- Legal Team: legal@markcubancompanies.com

**Vendor Support:**
- Azure: [Support Portal](https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade)
- Make.com: support@make.com
- Tally: support@tally.so

---

*Deployment Guide Version: 1.0*
*Last Updated: 2025-08-08*
*Next Review: Post-Launch + 30 days*