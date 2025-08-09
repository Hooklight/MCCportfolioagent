"""
Azure Function for MCC Portfolio Email Ingestion Pipeline
Monitors Finance@markcubancompanies.com for portfolio updates via Graph API
"""

import os
import json
import logging
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import base64

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import requests
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dateutil import parser as date_parser

# Configuration from environment variables
TENANT_ID = os.environ['AZURE_TENANT_ID']
CLIENT_ID = os.environ['AZURE_CLIENT_ID']
CLIENT_SECRET = os.environ['AZURE_CLIENT_SECRET']
DB_CONNECTION_STRING = os.environ['POSTGRES_CONNECTION_STRING']
SHAREPOINT_SITE_URL = os.environ['SHAREPOINT_SITE_URL']
STORAGE_ACCOUNT_NAME = os.environ['STORAGE_ACCOUNT_NAME']
STORAGE_CONTAINER = 'portfolio-artifacts'

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompanyMatcher:
    """Matches emails to companies using domain and entity recognition"""
    
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.company_cache = self._load_company_mappings()
    
    def _load_company_mappings(self) -> Dict[str, str]:
        """Load company domain mappings from database"""
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT company_id, legal_name, aka, website 
                FROM portfolio.company
            """)
            mappings = {}
            for row in cur.fetchall():
                # Extract domain from website
                if row['website']:
                    domain = re.findall(r'(?:https?://)?(?:www\.)?([^/]+)', row['website'])
                    if domain:
                        mappings[domain[0].lower()] = row['company_id']
                
                # Map company names
                mappings[row['legal_name'].lower()] = row['company_id']
                if row['aka']:
                    mappings[row['aka'].lower()] = row['company_id']
            
            return mappings
    
    def match_company(self, email_from: str, subject: str, body: str) -> Optional[str]:
        """Match email to company_id"""
        # Try domain match first
        sender_domain = email_from.split('@')[1].lower() if '@' in email_from else None
        if sender_domain and sender_domain in self.company_cache:
            return self.company_cache[sender_domain]
        
        # Try subject/body entity extraction
        text = f"{subject} {body}".lower()
        for company_name, company_id in self.company_cache.items():
            if company_name in text:
                return company_id
        
        # Log unmapped email for review
        logger.warning(f"Could not match email from {email_from} to any company")
        return None

class PortfolioDataExtractor:
    """Extracts structured portfolio data from email content"""
    
    AMOUNT_PATTERNS = [
        r'\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',  # $1,234,567.89
        r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*(?:USD|dollars?)',  # 1234567.89 USD
        r'([0-9]+(?:\.[0-9]+)?)[kKmMbB](?:\s*(?:USD|dollars?))?',  # 1.5M, 500k
    ]
    
    DATE_KEYWORDS = {
        'close_date': ['closed', 'closing date', 'close date', 'completed on'],
        'as_of_date': ['as of', 'as at', 'ownership as of', 'cap table dated'],
        'period': ['for the period', 'quarter ending', 'month ending', 'YTD through']
    }
    
    @staticmethod
    def extract_amounts(text: str) -> List[Tuple[Decimal, int]]:
        """Extract monetary amounts with confidence scores"""
        amounts = []
        
        for pattern in PortfolioDataExtractor.AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text):
                amount_str = match.group(1)
                amount_str = amount_str.replace(',', '')
                
                # Handle k/M/B notation
                if match.group(0)[-1].lower() in 'kmb':
                    multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
                    amount = Decimal(amount_str) * multipliers[match.group(0)[-1].lower()]
                else:
                    amount = Decimal(amount_str)
                
                # Confidence based on context
                confidence = 90
                context = text[max(0, match.start()-50):min(len(text), match.end()+50)]
                if any(kw in context.lower() for kw in ['invested', 'investment', 'amount']):
                    confidence = 95
                if any(kw in context.lower() for kw in ['pre-money', 'post-money', 'valuation']):
                    confidence = 85
                
                amounts.append((amount, confidence))
        
        return amounts
    
    @staticmethod
    def extract_dates(text: str) -> Dict[str, datetime]:
        """Extract dates with context"""
        dates = {}
        
        for date_type, keywords in PortfolioDataExtractor.DATE_KEYWORDS.items():
            for keyword in keywords:
                pattern = rf"{keyword}[:\s]*([A-Za-z]+ \d{{1,2}},? \d{{4}}|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}})"
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        parsed_date = date_parser.parse(match.group(1))
                        dates[date_type] = parsed_date
                        break
                    except:
                        continue
                if date_type in dates:
                    break
        
        return dates
    
    @staticmethod
    def extract_ownership(text: str) -> Optional[Dict]:
        """Extract ownership percentage"""
        patterns = [
            r'([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:ownership|equity|stake)',
            r'(?:owns?|holding?)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
            r'fully[\s-]diluted\s*(?:ownership|basis)?\s*(?:of\s*)?([0-9]+(?:\.[0-9]+)?)\s*%'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    'fully_diluted_pct': Decimal(match.group(1)),
                    'confidence': 0.85
                }
        
        return None
    
    @staticmethod
    def extract_metrics(text: str) -> Dict[str, Any]:
        """Extract KPI metrics from update emails"""
        metrics = {}
        
        metric_patterns = {
            'ARR': r'ARR[:\s]*\$?([0-9,]+(?:\.[0-9]+)?[kKmM]?)',
            'revenue': r'revenue[:\s]*\$?([0-9,]+(?:\.[0-9]+)?[kKmM]?)',
            'runway_months': r'runway[:\s]*([0-9]+)\s*months?',
            'headcount': r'(?:headcount|employees?|team size)[:\s]*([0-9]+)',
            'burn_rate': r'burn\s*(?:rate)?[:\s]*\$?([0-9,]+(?:\.[0-9]+)?[kKmM]?)',
            'cash': r'cash\s*(?:balance)?[:\s]*\$?([0-9,]+(?:\.[0-9]+)?[kKmM]?)',
            'churn': r'churn[:\s]*([0-9]+(?:\.[0-9]+)?)\s*%',
        }
        
        for metric, pattern in metric_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                # Normalize k/M notation
                if value[-1].lower() in 'km':
                    multipliers = {'k': 1000, 'm': 1000000}
                    value = str(float(value[:-1].replace(',', '')) * multipliers[value[-1].lower()])
                else:
                    value = value.replace(',', '')
                
                metrics[metric] = value
        
        return metrics

    def extract_from_email(self, email_data: Dict) -> Dict:
        """Main extraction function"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        from_email = email_data.get('from', {}).get('emailAddress', {}).get('address', '')
        message_id = email_data.get('id', '')
        received_date = email_data.get('receivedDateTime', '')
        
        full_text = f"{subject}\n{body}"
        
        # Classify email type
        email_type = self._classify_email(subject, body)
        
        # Initialize extraction result
        result = {
            'company_id': None,
            'source_ptr': {
                'source_type': 'email',
                'source_id': message_id,
                'storage_url': f"graph://messages/{message_id}"
            },
            'facts': {
                'company': {},
                'rounds': [],
                'ownerships': [],
                'cashflows': [],
                'updates': [],
                'contacts': [],
                'documents': []
            },
            'confidence_overall': 0.0,
            'spans': [],
            'anomalies': [],
            'assumptions': ['currency defaulted to USD']
        }
        
        # Extract based on email type
        if email_type == 'UPDATE':
            self._extract_update(full_text, result, received_date)
        elif email_type == 'FINANCIALS':
            self._extract_financials(full_text, result)
        elif email_type == 'BOARD':
            self._extract_board_materials(full_text, result)
        elif email_type == 'NOTEBOOKLM':
            self._extract_notebook_lm(full_text, result)
        elif email_type == 'CAPTABLE':
            self._extract_cap_table(full_text, result)
        
        # Extract common elements
        amounts = self.extract_amounts(full_text)
        dates = self.extract_dates(full_text)
        ownership = self.extract_ownership(full_text)
        
        # Add extracted data to result
        if amounts:
            for amount, confidence in amounts:
                if 'invested' in full_text.lower():
                    result['facts']['cashflows'].append({
                        'date': dates.get('close_date', datetime.now()).isoformat(),
                        'kind': 'Investment',
                        'amount': str(amount),
                        'confidence': confidence / 100
                    })
        
        if ownership:
            result['facts']['ownerships'].append({
                'as_of_date': dates.get('as_of_date', datetime.now()).isoformat(),
                'fully_diluted_pct': str(ownership['fully_diluted_pct']),
                'confidence': ownership['confidence']
            })
        
        # Calculate overall confidence
        confidences = []
        for fact_type in result['facts'].values():
            if isinstance(fact_type, list):
                for item in fact_type:
                    if isinstance(item, dict) and 'confidence' in item:
                        confidences.append(item['confidence'])
        
        result['confidence_overall'] = sum(confidences) / len(confidences) if confidences else 0.5
        
        return result
    
    def _classify_email(self, subject: str, body: str) -> str:
        """Classify email type based on content"""
        subject_lower = subject.lower()
        
        if '[update]' in subject_lower or 'monthly update' in subject_lower:
            return 'UPDATE'
        elif '[financials]' in subject_lower or 'financial statements' in body.lower():
            return 'FINANCIALS'
        elif '[board]' in subject_lower or 'board deck' in body.lower():
            return 'BOARD'
        elif '[notebooklm]' in subject_lower or 'notebook lm' in body.lower():
            return 'NOTEBOOKLM'
        elif '[captable]' in subject_lower or 'cap table' in body.lower():
            return 'CAPTABLE'
        else:
            return 'GENERAL'
    
    def _extract_update(self, text: str, result: Dict, received_date: str):
        """Extract company update information"""
        metrics = self.extract_metrics(text)
        dates = self.extract_dates(text)
        
        # Determine report period
        period_end = dates.get('period', date_parser.parse(received_date))
        period_start = period_end - timedelta(days=30)  # Default to monthly
        
        # Extract quarter if mentioned
        quarter_match = re.search(r'Q([1-4])\s*(\d{4})', text)
        if quarter_match:
            quarter = int(quarter_match.group(1))
            year = int(quarter_match.group(2))
            report_period = f"{year}-Q{quarter}"
        else:
            report_period = period_end.strftime("%Y-%m")
        
        result['facts']['updates'].append({
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'report_period': report_period,
            'metrics': metrics,
            'qualitative_summary': text[:500],  # First 500 chars as summary
            'confidence': 0.8
        })
    
    def _extract_financials(self, text: str, result: Dict):
        """Extract financial statement data"""
        # Similar extraction logic for financial statements
        pass
    
    def _extract_board_materials(self, text: str, result: Dict):
        """Extract board deck information"""
        # Similar extraction logic for board materials
        pass
    
    def _extract_notebook_lm(self, text: str, result: Dict):
        """Extract Notebook LM summary data"""
        # Extract decisions, commitments, KPIs
        result['facts']['comm'] = [{
            'source': 'notebook_lm',
            'occurred_at': datetime.now().isoformat(),
            'summary': text[:1000],
            'extracted_fields': self.extract_metrics(text),
            'confidence': 0.7  # Lower confidence for AI-generated summaries
        }]
    
    def _extract_cap_table(self, text: str, result: Dict):
        """Extract cap table information"""
        ownership = self.extract_ownership(text)
        if ownership:
            result['facts']['ownerships'].append({
                'as_of_date': datetime.now().isoformat(),
                'fully_diluted_pct': str(ownership['fully_diluted_pct']),
                'confidence': ownership['confidence']
            })

class DataPersister:
    """Handles database persistence and SharePoint storage"""
    
    def __init__(self, db_conn, storage_client):
        self.db_conn = db_conn
        self.storage_client = storage_client
    
    def persist_extraction(self, extraction_result: Dict) -> Dict:
        """Persist extracted data to database and storage"""
        company_id = extraction_result['company_id']
        
        if not company_id:
            logger.warning("No company_id found, skipping persistence")
            return {'status': 'skipped', 'reason': 'no_company_id'}
        
        records_created = {
            'company': 0,
            'rounds': 0,
            'ownerships': 0,
            'cashflows': 0,
            'updates': 0,
            'contacts': 0,
            'documents': 0
        }
        
        try:
            with self.db_conn.cursor() as cur:
                # Persist each fact type
                facts = extraction_result['facts']
                
                # Cashflows
                for cf in facts.get('cashflows', []):
                    cur.execute("""
                        INSERT INTO portfolio.cashflow 
                        (company_id, date, kind, amount, source_type, source_id, extraction_confidence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_id, date, amount, wire_ref) DO NOTHING
                        RETURNING cashflow_id
                    """, (
                        company_id,
                        cf.get('date'),
                        cf.get('kind'),
                        cf.get('amount'),
                        extraction_result['source_ptr']['source_type'],
                        extraction_result['source_ptr']['source_id'],
                        cf.get('confidence', 0.5)
                    ))
                    if cur.fetchone():
                        records_created['cashflows'] += 1
                
                # Ownership
                for own in facts.get('ownerships', []):
                    cur.execute("""
                        INSERT INTO portfolio.ownership
                        (company_id, as_of_date, fully_diluted_pct, source_type, source_id, extraction_confidence)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_id, as_of_date, security_class) DO UPDATE
                        SET fully_diluted_pct = EXCLUDED.fully_diluted_pct,
                            extraction_confidence = EXCLUDED.extraction_confidence,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING ownership_id
                    """, (
                        company_id,
                        own.get('as_of_date'),
                        own.get('fully_diluted_pct'),
                        extraction_result['source_ptr']['source_type'],
                        extraction_result['source_ptr']['source_id'],
                        own.get('confidence', 0.5)
                    ))
                    if cur.fetchone():
                        records_created['ownerships'] += 1
                
                # Updates
                for update in facts.get('updates', []):
                    cur.execute("""
                        INSERT INTO portfolio.update
                        (company_id, period_start, period_end, report_period, metrics, 
                         qualitative_summary, confidence, source_type, source_id, extraction_confidence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING update_id
                    """, (
                        company_id,
                        update.get('period_start'),
                        update.get('period_end'),
                        update.get('report_period'),
                        Json(update.get('metrics', {})),
                        update.get('qualitative_summary'),
                        update.get('confidence', 0.5),
                        extraction_result['source_ptr']['source_type'],
                        extraction_result['source_ptr']['source_id'],
                        update.get('confidence', 0.5)
                    ))
                    if cur.fetchone():
                        records_created['updates'] += 1
                
                # Log ingestion
                cur.execute("""
                    INSERT INTO portfolio.ingestion_log
                    (source_type, source_id, company_id, records_created, confidence_scores, 
                     anomalies, assumptions, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    extraction_result['source_ptr']['source_type'],
                    extraction_result['source_ptr']['source_id'],
                    company_id,
                    Json(records_created),
                    Json({'overall': extraction_result['confidence_overall']}),
                    extraction_result.get('anomalies', []),
                    extraction_result.get('assumptions', []),
                    'success'
                ))
                
                self.db_conn.commit()
                
        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Database persistence failed: {str(e)}")
            raise
        
        return {
            'status': 'success',
            'records_created': records_created
        }
    
    def save_to_sharepoint(self, company_id: str, content: bytes, filename: str, doc_type: str) -> str:
        """Save document to SharePoint/Blob Storage"""
        # Generate path
        folder = {
            'email': 'Email-Exports',
            'update': 'Updates',
            'financial': 'Finance',
            'legal': 'Legal'
        }.get(doc_type, 'Documents')
        
        blob_path = f"Portfolio/{company_id}/{folder}/{filename}"
        
        # Upload to blob storage
        blob_client = self.storage_client.get_blob_client(
            container=STORAGE_CONTAINER,
            blob=blob_path
        )
        blob_client.upload_blob(content, overwrite=True)
        
        return f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{STORAGE_CONTAINER}/{blob_path}"

def main(msg: func.QueueMessage) -> None:
    """Azure Function entry point"""
    logger.info('Processing email message from queue')
    
    # Parse message
    message_data = json.loads(msg.get_body().decode('utf-8'))
    
    # Initialize connections
    db_conn = psycopg2.connect(DB_CONNECTION_STRING)
    storage_client = BlobServiceClient.from_connection_string(
        os.environ['AZURE_STORAGE_CONNECTION_STRING']
    )
    
    try:
        # Initialize components
        matcher = CompanyMatcher(db_conn)
        extractor = PortfolioDataExtractor()
        persister = DataPersister(db_conn, storage_client)
        
        # Get email details from Graph API
        email_data = get_email_from_graph(message_data['messageId'])
        
        # Match to company
        company_id = matcher.match_company(
            email_data.get('from', {}).get('emailAddress', {}).get('address', ''),
            email_data.get('subject', ''),
            email_data.get('body', '')
        )
        
        # Extract structured data
        extraction_result = extractor.extract_from_email(email_data)
        extraction_result['company_id'] = company_id
        
        # Save email to SharePoint
        if company_id:
            email_json = json.dumps(email_data, indent=2).encode('utf-8')
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message_data['messageId'][:8]}.json"
            storage_url = persister.save_to_sharepoint(company_id, email_json, filename, 'email')
            
            # Save attachments
            for attachment in email_data.get('attachments', []):
                att_content = base64.b64decode(attachment['contentBytes'])
                att_url = persister.save_to_sharepoint(
                    company_id, 
                    att_content, 
                    attachment['name'],
                    'update' if 'update' in attachment['name'].lower() else 'document'
                )
                extraction_result['facts']['documents'].append({
                    'doc_id': attachment['id'],
                    'storage_url': att_url,
                    'title': attachment['name'],
                    'doc_type': attachment.get('contentType', 'unknown')
                })
        
        # Persist to database
        result = persister.persist_extraction(extraction_result)
        
        logger.info(f"Successfully processed email. Result: {result}")
        
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        raise
    finally:
        db_conn.close()

def get_email_from_graph(message_id: str) -> Dict:
    """Fetch email details from Microsoft Graph API"""
    # Get access token
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials'
    }
    token_response = requests.post(token_url, data=token_data)
    access_token = token_response.json()['access_token']
    
    # Fetch email with attachments
    headers = {'Authorization': f'Bearer {access_token}'}
    email_url = f"https://graph.microsoft.com/v1.0/users/Finance@markcubancompanies.com/messages/{message_id}?$expand=attachments"
    
    response = requests.get(email_url, headers=headers)
    return response.json()

# Function.json configuration
FUNCTION_CONFIG = {
    "scriptFile": "__init__.py",
    "bindings": [
        {
            "name": "msg",
            "type": "queueTrigger",
            "direction": "in",
            "queueName": "email-ingestion-queue",
            "connection": "AzureWebJobsStorage"
        }
    ]
}