#!/usr/bin/env python3
"""
Robust CSV Parser for MCC Legal Team Spreadsheets
Handles encoding detection, header variations, and data normalization
"""

import csv
import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import chardet
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dateutil import parser as date_parser
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RobustCSVParser:
    """Parse messy CSV/Excel files with encoding detection and flexible column mapping"""
    
    # Known column variations for mapping
    COLUMN_MAPPINGS = {
        'company': [
            'Name of Company', 'Company Name', 'Company', 'Portfolio Company',
            'Legal Name', 'Entity', 'Investment Name', 'Name'
        ],
        'amount_invested': [
            'Total Amount Invested', 'Investment Amount', 'Amount Invested',
            'Total Investment', 'MCC Investment', 'Amount', 'Investment',
            'Total $ Invested', 'Investment ($)', 'Amount (USD)'
        ],
        'date': [
            'Earliest Date of Investment', 'Investment Date', 'Close Date',
            'First Investment Date', 'Initial Investment', 'Date', 'Closing Date',
            'Transaction Date', 'Earliest Date'
        ],
        'ownership': [
            'Equity %', 'Ownership %', 'Ownership Percentage', 'Equity Percentage',
            'MCC Ownership', '% Ownership', 'Equity', 'Stake', 'Ownership'
        ],
        'round_type': [
            'Round Type', 'Investment Type', 'Type', 'Round', 'Series',
            'Investment Round', 'Stage'
        ],
        'valuation': [
            'Pre-Money Valuation', 'Pre Money', 'Valuation', 'Pre-Money',
            'Company Valuation', 'Val'
        ],
        'status': [
            'Status', 'Company Status', 'Current Status', 'Investment Status',
            'Active/Inactive', 'State'
        ],
        'distributions': [
            'Distributions', 'Total Distributions', 'Distribution Amount',
            'Distributions to Date', 'Cash Distributed', 'Returns'
        ]
    }
    
    # Encodings to try in order
    ENCODING_PRIORITY = [
        'utf-8', 'utf-8-sig', 'cp1252', 'windows-1252', 
        'latin-1', 'iso-8859-1', 'mac-roman'
    ]
    
    def __init__(self, db_connection_string: str):
        self.db_conn = psycopg2.connect(db_connection_string) if db_connection_string else None
        self.reconciliation_log = []
        self.company_lookup = self._build_company_lookup()
    
    def _build_company_lookup(self) -> Dict[str, str]:
        """Build fuzzy matching lookup for company names"""
        if not self.db_conn:
            return {}
        
        lookup = {}
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT company_id, legal_name, aka FROM portfolio.company")
            for row in cur.fetchall():
                # Normalize for matching
                lookup[self._normalize_company_name(row['legal_name'])] = row['company_id']
                if row['aka']:
                    lookup[self._normalize_company_name(row['aka'])] = row['company_id']
        
        return lookup
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for matching"""
        if not name:
            return ''
        
        # Remove common suffixes
        name = re.sub(r'\b(LLC|Inc|Corp|Corporation|Ltd|Limited|Co|Company)\b', '', name, flags=re.IGNORECASE)
        # Remove punctuation and extra spaces
        name = re.sub(r'[^\w\s]', '', name)
        name = ' '.join(name.split())
        
        return name.lower().strip()
    
    def detect_encoding(self, file_path: str) -> str:
        """Detect file encoding with multiple strategies"""
        # Try chardet first
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            if result['confidence'] > 0.8:
                return result['encoding']
        
        # Try each encoding in priority order
        for encoding in self.ENCODING_PRIORITY:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1000)  # Try reading first 1000 chars
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        # Default to latin-1 (can decode anything)
        return 'latin-1'
    
    def find_header_row(self, df: pd.DataFrame) -> int:
        """Find the actual header row in a messy spreadsheet"""
        # Look for row with multiple expected column names
        for idx, row in df.iterrows():
            if idx > 20:  # Don't search too far
                break
            
            row_str = ' '.join(str(val) for val in row if pd.notna(val))
            matches = 0
            
            for column_list in self.COLUMN_MAPPINGS.values():
                if any(col in row_str for col in column_list):
                    matches += 1
            
            if matches >= 3:  # Found at least 3 expected columns
                return idx
        
        return 0  # Default to first row
    
    def map_columns(self, df_columns: List[str]) -> Dict[str, str]:
        """Map messy column names to canonical names"""
        mapping = {}
        
        for col in df_columns:
            col_clean = str(col).strip()
            
            for canonical_name, variations in self.COLUMN_MAPPINGS.items():
                for variation in variations:
                    if variation.lower() in col_clean.lower():
                        mapping[col] = canonical_name
                        break
                if col in mapping:
                    break
        
        return mapping
    
    def clean_currency(self, value: Any) -> Optional[Decimal]:
        """Clean and parse currency values"""
        if pd.isna(value) or value == '' or value is None:
            return None
        
        value_str = str(value)
        
        # Remove currency symbols and whitespace
        value_str = re.sub(r'[$,\s]', '', value_str)
        
        # Handle parentheses for negative values
        if value_str.startswith('(') and value_str.endswith(')'):
            value_str = '-' + value_str[1:-1]
        
        # Handle K/M/B notation
        multiplier = 1
        if value_str.endswith(('k', 'K')):
            multiplier = 1000
            value_str = value_str[:-1]
        elif value_str.endswith(('m', 'M')):
            multiplier = 1000000
            value_str = value_str[:-1]
        elif value_str.endswith(('b', 'B')):
            multiplier = 1000000000
            value_str = value_str[:-1]
        
        try:
            return Decimal(value_str) * multiplier
        except (ValueError, TypeError, decimal.InvalidOperation):
            logger.warning(f"Could not parse currency value: {value}")
            return None
    
    def clean_percentage(self, value: Any) -> Optional[Decimal]:
        """Clean and parse percentage values"""
        if pd.isna(value) or value == '' or value is None:
            return None
        
        value_str = str(value).strip()
        value_str = value_str.replace('%', '').replace(',', '')
        
        try:
            pct = Decimal(value_str)
            # If value is > 1, assume it's already a percentage (e.g., 15 means 15%)
            # If value is <= 1, assume it's a decimal (e.g., 0.15 means 15%)
            if pct <= 1:
                pct = pct * 100
            return pct
        except (ValueError, TypeError, decimal.InvalidOperation):
            logger.warning(f"Could not parse percentage value: {value}")
            return None
    
    def parse_date(self, value: Any) -> Optional[datetime]:
        """Parse various date formats"""
        if pd.isna(value) or value == '' or value is None:
            return None
        
        # Handle Excel serial dates
        if isinstance(value, (int, float)):
            try:
                # Excel epoch is 1900-01-01
                return datetime(1900, 1, 1) + timedelta(days=int(value) - 2)
            except:
                pass
        
        # Try standard date parsing
        try:
            return date_parser.parse(str(value))
        except:
            logger.warning(f"Could not parse date value: {value}")
            return None
    
    def parse_file(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse CSV/Excel file and return structured data + reconciliation report"""
        file_path = Path(file_path)
        logger.info(f"Parsing file: {file_path}")
        
        # Detect file type and read accordingly
        if file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, header=None)
        else:
            encoding = self.detect_encoding(str(file_path))
            logger.info(f"Detected encoding: {encoding}")
            df = pd.read_csv(file_path, header=None, encoding=encoding)
        
        # Find actual header row
        header_row = self.find_header_row(df)
        logger.info(f"Found header at row: {header_row}")
        
        # Reset dataframe with correct header
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row + 1:].reset_index(drop=True)
        
        # Remove total/summary rows (usually at the end)
        df = df[~df.iloc[:, 0].astype(str).str.contains('Total|Summary|Grand', case=False, na=False)]
        
        # Map columns
        column_mapping = self.map_columns(df.columns.tolist())
        logger.info(f"Column mapping: {column_mapping}")
        
        # Process each row
        extracted_data = []
        
        for idx, row in df.iterrows():
            try:
                # Skip empty rows
                if pd.isna(row.get(next(iter(column_mapping.keys()), None))):
                    continue
                
                # Extract and clean data
                company_name = None
                for col, mapped in column_mapping.items():
                    if mapped == 'company':
                        company_name = str(row[col]).strip() if pd.notna(row[col]) else None
                        break
                
                if not company_name:
                    continue
                
                # Match to company_id
                normalized_name = self._normalize_company_name(company_name)
                company_id = self.company_lookup.get(normalized_name)
                
                if not company_id:
                    # Try fuzzy matching
                    for lookup_name, lookup_id in self.company_lookup.items():
                        if normalized_name in lookup_name or lookup_name in normalized_name:
                            company_id = lookup_id
                            break
                
                if not company_id:
                    # Generate slug from name
                    company_id = re.sub(r'[^\w\s-]', '', company_name.lower())
                    company_id = re.sub(r'[-\s]+', '-', company_id).strip('-')
                    
                    self.reconciliation_log.append({
                        'row': idx + header_row + 2,  # Excel row number
                        'company_name': company_name,
                        'issue': 'Company not found in database',
                        'suggested_id': company_id
                    })
                
                # Build record
                record = {
                    'company_id': company_id,
                    'company_name': company_name,
                    'source_row': idx + header_row + 2
                }
                
                # Extract financial data
                for col, mapped in column_mapping.items():
                    value = row[col]
                    
                    if mapped == 'amount_invested':
                        record['amount_invested'] = self.clean_currency(value)
                    elif mapped == 'distributions':
                        record['distributions'] = self.clean_currency(value)
                    elif mapped == 'ownership':
                        record['ownership_pct'] = self.clean_percentage(value)
                    elif mapped == 'date':
                        record['investment_date'] = self.parse_date(value)
                    elif mapped == 'round_type':
                        record['round_type'] = str(value).strip() if pd.notna(value) else None
                    elif mapped == 'valuation':
                        record['pre_money_valuation'] = self.clean_currency(value)
                    elif mapped == 'status':
                        record['status'] = str(value).strip().lower() if pd.notna(value) else 'active'
                
                # Validate record
                issues = []
                
                if record.get('amount_invested') and record.get('distributions'):
                    if record['distributions'] > record['amount_invested'] * 10:
                        issues.append('Distributions exceed 10x investment')
                
                if record.get('ownership_pct'):
                    if record['ownership_pct'] > 100:
                        issues.append(f"Ownership > 100%: {record['ownership_pct']}")
                    elif record['ownership_pct'] < 0:
                        issues.append(f"Negative ownership: {record['ownership_pct']}")
                
                if record.get('investment_date'):
                    if record['investment_date'] > datetime.now():
                        issues.append('Future investment date')
                    elif record['investment_date'] < datetime(1990, 1, 1):
                        issues.append('Investment date before 1990')
                
                if issues:
                    self.reconciliation_log.append({
                        'row': record['source_row'],
                        'company_name': company_name,
                        'issue': '; '.join(issues),
                        'data': record
                    })
                
                extracted_data.append(record)
                
            except Exception as e:
                logger.error(f"Error processing row {idx}: {str(e)}")
                self.reconciliation_log.append({
                    'row': idx + header_row + 2,
                    'error': str(e),
                    'raw_data': row.to_dict()
                })
        
        logger.info(f"Extracted {len(extracted_data)} records with {len(self.reconciliation_log)} issues")
        
        return extracted_data, self.reconciliation_log
    
    def persist_to_database(self, extracted_data: List[Dict]) -> Dict[str, int]:
        """Persist extracted data to database"""
        if not self.db_conn:
            logger.warning("No database connection, skipping persistence")
            return {}
        
        counts = {
            'companies': 0,
            'rounds': 0,
            'cashflows': 0,
            'ownerships': 0
        }
        
        try:
            with self.db_conn.cursor() as cur:
                for record in extracted_data:
                    company_id = record['company_id']
                    
                    # Upsert company
                    cur.execute("""
                        INSERT INTO portfolio.company (company_id, legal_name, status, source_type)
                        VALUES (%s, %s, %s, 'csv_import')
                        ON CONFLICT (company_id) DO UPDATE
                        SET status = COALESCE(EXCLUDED.status, company.status),
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING company_id
                    """, (company_id, record['company_name'], record.get('status', 'active')))
                    
                    if cur.fetchone():
                        counts['companies'] += 1
                    
                    # Insert investment as cashflow
                    if record.get('amount_invested'):
                        cur.execute("""
                            INSERT INTO portfolio.cashflow 
                            (company_id, date, kind, amount, source_type, notes)
                            VALUES (%s, %s, 'Investment', %s, 'csv_import', %s)
                            ON CONFLICT (company_id, date, amount, wire_ref) DO NOTHING
                            RETURNING cashflow_id
                        """, (
                            company_id,
                            record.get('investment_date', datetime.now().date()),
                            record['amount_invested'],
                            f"CSV import row {record['source_row']}"
                        ))
                        if cur.fetchone():
                            counts['cashflows'] += 1
                    
                    # Insert distributions
                    if record.get('distributions'):
                        cur.execute("""
                            INSERT INTO portfolio.cashflow 
                            (company_id, date, kind, amount, source_type, notes)
                            VALUES (%s, %s, 'Distribution', %s, 'csv_import', %s)
                            ON CONFLICT (company_id, date, amount, wire_ref) DO NOTHING
                            RETURNING cashflow_id
                        """, (
                            company_id,
                            datetime.now().date(),  # No distribution date in CSV
                            record['distributions'],
                            f"CSV import row {record['source_row']} - cumulative distributions"
                        ))
                        if cur.fetchone():
                            counts['cashflows'] += 1
                    
                    # Insert ownership
                    if record.get('ownership_pct'):
                        cur.execute("""
                            INSERT INTO portfolio.ownership
                            (company_id, as_of_date, fully_diluted_pct, source_type, notes)
                            VALUES (%s, %s, %s, 'csv_import', %s)
                            ON CONFLICT (company_id, as_of_date, security_class) DO UPDATE
                            SET fully_diluted_pct = EXCLUDED.fully_diluted_pct,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING ownership_id
                        """, (
                            company_id,
                            record.get('investment_date', datetime.now().date()),
                            record['ownership_pct'],
                            f"CSV import row {record['source_row']}"
                        ))
                        if cur.fetchone():
                            counts['ownerships'] += 1
                    
                    # Insert round if we have the data
                    if record.get('amount_invested') and record.get('investment_date'):
                        cur.execute("""
                            INSERT INTO portfolio.round
                            (company_id, type, close_date, amount_invested_by_mcc, 
                             pre_money, source_type)
                            VALUES (%s, %s, %s, %s, %s, 'csv_import')
                            RETURNING round_id
                        """, (
                            company_id,
                            record.get('round_type', 'Unknown'),
                            record['investment_date'],
                            record['amount_invested'],
                            record.get('pre_money_valuation')
                        ))
                        if cur.fetchone():
                            counts['rounds'] += 1
                
                self.db_conn.commit()
                logger.info(f"Successfully persisted: {counts}")
                
        except Exception as e:
            self.db_conn.rollback()
            logger.error(f"Database persistence failed: {str(e)}")
            raise
        
        return counts
    
    def generate_reconciliation_report(self, output_path: str):
        """Generate reconciliation CSV report"""
        if not self.reconciliation_log:
            logger.info("No reconciliation issues to report")
            return
        
        df = pd.DataFrame(self.reconciliation_log)
        df.to_csv(output_path, index=False)
        logger.info(f"Reconciliation report saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Parse MCC portfolio CSV/Excel files')
    parser.add_argument('input_file', help='Path to CSV or Excel file')
    parser.add_argument('--db-connection', help='PostgreSQL connection string', 
                       default=os.environ.get('POSTGRES_CONNECTION_STRING'))
    parser.add_argument('--reconciliation-output', help='Path for reconciliation report',
                       default='reconciliation_report.csv')
    parser.add_argument('--dry-run', action='store_true', help='Parse without persisting to database')
    
    args = parser.parse_args()
    
    # Initialize parser
    csv_parser = RobustCSVParser(args.db_connection if not args.dry_run else None)
    
    # Parse file
    extracted_data, reconciliation_log = csv_parser.parse_file(args.input_file)
    
    # Display summary
    print(f"\n📊 Parsing Summary:")
    print(f"  ✓ Records extracted: {len(extracted_data)}")
    print(f"  ⚠ Issues found: {len(reconciliation_log)}")
    
    if extracted_data:
        # Show sample data
        print(f"\n📝 Sample extracted data (first 3 records):")
        for record in extracted_data[:3]:
            print(f"  - {record['company_name']}: ${record.get('amount_invested', 0):,.0f}")
    
    if reconciliation_log:
        print(f"\n⚠️ Sample issues (first 5):")
        for issue in reconciliation_log[:5]:
            print(f"  - Row {issue.get('row', '?')}: {issue.get('issue', issue.get('error', 'Unknown'))}")
    
    # Persist to database
    if not args.dry_run and args.db_connection:
        print(f"\n💾 Persisting to database...")
        counts = csv_parser.persist_to_database(extracted_data)
        print(f"  ✓ Persisted: {counts}")
    
    # Generate reconciliation report
    csv_parser.generate_reconciliation_report(args.reconciliation_output)
    print(f"\n📄 Reconciliation report saved to: {args.reconciliation_output}")

if __name__ == "__main__":
    import os
    from datetime import timedelta
    import decimal
    
    main()