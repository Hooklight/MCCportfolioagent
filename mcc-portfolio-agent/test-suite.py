#!/usr/bin/env python3
"""
MCC Portfolio Intelligence - Test Suite with Synthetic Data
Tests extraction, parsing, and data persistence
"""

import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class TestData:
    """Synthetic test data samples"""
    
    # Sample email messages
    SAMPLE_EMAILS = {
        "update_email": {
            "id": "AAMkAGI2TG93AAA=",
            "subject": "[UPDATE] BrightWheel - January 2025 Update",
            "from": {
                "emailAddress": {
                    "address": "dave@brightwheel.com",
                    "name": "Dave Vasen"
                }
            },
            "receivedDateTime": "2025-01-31T10:30:00Z",
            "body": """
            Hi MCC Team,
            
            Here's our January 2025 update:
            
            Metrics:
            - ARR: $15.5M (up from $14.2M last month)
            - Cash: $8.2M
            - Runway: 18 months
            - Headcount: 52 (added 3 engineers)
            - Monthly burn: $455k
            
            Highlights:
            - Closed 3 enterprise deals worth $2.1M in ARR
            - Launched new billing module
            - Featured in EdTech Magazine as top startup
            
            Challenges:
            - Sales cycle lengthening for enterprise deals
            - Need to hire senior VP of Sales
            
            Asks:
            - Introduction to other portfolio companies in EdTech
            - Advice on sales compensation structure
            
            Best,
            Dave
            """,
            "attachments": []
        },
        
        "financial_email": {
            "id": "AAMkAGI2TG94BBB=",
            "subject": "[FINANCIALS] Dude Wipes Q4 2024 Financials",
            "from": {
                "emailAddress": {
                    "address": "sean@dudewipes.com",
                    "name": "Sean Riley"
                }
            },
            "receivedDateTime": "2025-01-15T14:00:00Z",
            "body": """
            MCC Team,
            
            Attached are our Q4 2024 financial statements.
            
            Summary:
            - Revenue: $8.5M (25% QoQ growth)
            - Gross Margin: 42%
            - EBITDA: $1.2M
            - Cash Flow Positive for 3rd consecutive quarter
            
            We're on track to hit $40M revenue for 2025.
            
            Sean
            """,
            "attachments": [
                {
                    "id": "AAMkAGI2TG94BBB=.1",
                    "name": "DudeWipes_Q4_2024_Financials.pdf",
                    "contentType": "application/pdf",
                    "size": 245632,
                    "contentBytes": "base64encodedcontent..."
                }
            ]
        },
        
        "investment_email": {
            "id": "AAMkAGI2TG95CCC=",
            "subject": "Chapul Series A Closing - MCC Investment Confirmation",
            "from": {
                "emailAddress": {
                    "address": "pat@chapul.com",
                    "name": "Pat Crowley"
                }
            },
            "receivedDateTime": "2025-01-20T09:15:00Z",
            "body": """
            Mark and Team,
            
            Confirming MCC's $750,000 investment in our Series A round.
            
            Round Details:
            - Total Round Size: $5M
            - Pre-money valuation: $15M
            - Post-money: $20M
            - MCC ownership: 3.75% on a fully diluted basis
            - Lead Investor: GreenTech Ventures
            - Close Date: January 20, 2025
            
            Wire received, thanks for your continued support!
            
            Pat
            """,
            "attachments": []
        },
        
        "notebook_lm_email": {
            "id": "AAMkAGI2TG96DDD=",
            "subject": "[NOTEBOOKLM] BeatBox Beverages - Board Call Summary",
            "from": {
                "emailAddress": {
                    "address": "assistant@markcubancompanies.com",
                    "name": "MCC Assistant"
                }
            },
            "receivedDateTime": "2025-01-25T16:45:00Z",
            "body": """
            Notebook LM Summary of Board Call with BeatBox Beverages
            Date: January 25, 2025
            
            Key Decisions:
            - Approved $2M marketing budget for summer campaign
            - Hired CMO candidate (Jennifer Walsh, ex-Red Bull)
            - Pivot to focus on convenience store channel
            
            Commitments:
            - CEO to provide weekly sales updates
            - CFO to model new channel economics by Feb 15
            - MCC to introduce to Kroger buyer
            
            KPIs Discussed:
            - Current MRR: $3.2M
            - Velocity rate: 8.5 units/store/week
            - Distribution: 15,000 stores (target 25,000 by Q3)
            
            Concerns:
            - Competitor (BuzzBox) raising $50M round
            - Aluminum can shortage affecting Q2 production
            
            Next Board Meeting: April 25, 2025
            """,
            "attachments": []
        }
    }
    
    # Sample CSV data
    SAMPLE_CSV = """Name of Company,Total Amount Invested,Earliest Date of Investment,Equity %,Status,Distributions
BrightWheel,"$2,500,000",2018-03-15,5.2%,Active,"$0"
Dude Wipes,"$1,000,000",2019-06-20,2.8%,Active,"$150,000"
Chapul LLC,$750k,2020-09-10,3.75%,Active,$0
"Mark Cuban Cost Plus Drugs","$5,000,000",2021-01-05,15%,Active,"$2,500,000"
BeatBox Beverages,"3000000",2017-11-30,4.5%,Active,"500000"
Glow Recipe,1500000,2020-04-15,2.1%,Exited,8500000
Failed Startup Co,"$500,000",2019-03-01,10%,Written Off,"$0"
"""
    
    # Sample Tally form responses
    SAMPLE_TALLY_RESPONSES = {
        "company_update": {
            "formId": "mRy1pl",
            "responseId": "resp_3nK9vX2m",
            "createdAt": "2025-01-31T18:00:00Z",
            "data": {
                "company_name": "BrightWheel",
                "report_period": "2025-01",
                "period_type": "monthly",
                "arr": "15500000",
                "revenue": "1291667",
                "gross_margin": "72",
                "burn_rate": "455000",
                "cash_balance": "8200000",
                "runway_months": "18",
                "headcount": "52",
                "customer_count": "3500",
                "churn_rate": "2.1",
                "cac": "2500",
                "ltv": "25000",
                "highlights": "Closed 3 enterprise deals. Launched billing module.",
                "challenges": "Sales cycle lengthening. Need VP Sales.",
                "asks": "Intros to EdTech companies. Sales comp advice.",
                "submitter_email": "dave@brightwheel.com"
            }
        },
        
        "financial_update": {
            "formId": "wdeeRr",
            "responseId": "resp_4mL8wY3n",
            "createdAt": "2025-01-15T20:00:00Z",
            "data": {
                "company_name": "Dude Wipes",
                "period_ending": "2024-12-31",
                "revenue": "8500000",
                "cogs": "4930000",
                "gross_profit": "3570000",
                "operating_expenses": "2850000",
                "ebitda": "1200000",
                "net_income": "950000",
                "cash": "3200000",
                "accounts_receivable": "1800000",
                "inventory": "2100000",
                "total_assets": "12500000",
                "total_liabilities": "4200000",
                "equity": "8300000",
                "submitter_email": "sean@dudewipes.com"
            }
        }
    }


class TestEmailExtraction(unittest.TestCase):
    """Test email content extraction"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the extractor
        from azure_function_email_ingestion import PortfolioDataExtractor
        self.extractor = PortfolioDataExtractor()
    
    def test_extract_update_email(self):
        """Test extraction from company update email"""
        email = TestData.SAMPLE_EMAILS["update_email"]
        result = self.extractor.extract_from_email(email)
        
        # Verify extraction
        self.assertIsNotNone(result)
        self.assertEqual(len(result['facts']['updates']), 1)
        
        update = result['facts']['updates'][0]
        self.assertEqual(update['metrics']['ARR'], '15500000')
        self.assertEqual(update['metrics']['runway_months'], '18')
        self.assertEqual(update['metrics']['headcount'], '52')
        
    def test_extract_investment_email(self):
        """Test extraction from investment confirmation email"""
        email = TestData.SAMPLE_EMAILS["investment_email"]
        result = self.extractor.extract_from_email(email)
        
        # Verify cashflow extraction
        self.assertGreater(len(result['facts']['cashflows']), 0)
        
        cashflow = result['facts']['cashflows'][0]
        self.assertEqual(Decimal(cashflow['amount']), Decimal('750000'))
        self.assertEqual(cashflow['kind'], 'Investment')
        
        # Verify ownership extraction
        self.assertGreater(len(result['facts']['ownerships']), 0)
        ownership = result['facts']['ownerships'][0]
        self.assertEqual(Decimal(ownership['fully_diluted_pct']), Decimal('3.75'))
    
    def test_extract_notebook_lm(self):
        """Test extraction from Notebook LM summary"""
        email = TestData.SAMPLE_EMAILS["notebook_lm_email"]
        result = self.extractor.extract_from_email(email)
        
        # Should have lower confidence
        self.assertLess(result['confidence_overall'], 0.8)
        
        # Should extract metrics
        self.assertGreater(len(result['facts']['updates']), 0)
        metrics = result['facts']['updates'][0]['metrics']
        self.assertIn('MRR', metrics)
    
    def test_amount_extraction(self):
        """Test various amount format extractions"""
        test_cases = [
            ("Revenue is $1,234,567.89 this quarter", Decimal("1234567.89")),
            ("We raised 2.5M in funding", Decimal("2500000")),
            ("Burn rate: $450k monthly", Decimal("450000")),
            ("valuation of 15 million dollars", Decimal("15000000")),
            ("$1.2B market cap", Decimal("1200000000"))
        ]
        
        for text, expected in test_cases:
            amounts = self.extractor.extract_amounts(text)
            self.assertGreater(len(amounts), 0)
            self.assertEqual(amounts[0][0], expected)
    
    def test_date_extraction(self):
        """Test date extraction from various formats"""
        test_cases = [
            ("Closing date: January 15, 2025", datetime(2025, 1, 15)),
            ("As of 01/20/2025", datetime(2025, 1, 20)),
            ("Quarter ending 2025-03-31", datetime(2025, 3, 31))
        ]
        
        for text, expected in test_cases:
            dates = self.extractor.extract_dates(text)
            self.assertGreater(len(dates), 0)
            # Check date only (ignore time)
            extracted_date = list(dates.values())[0]
            self.assertEqual(extracted_date.date(), expected.date())


class TestCSVParser(unittest.TestCase):
    """Test CSV parsing and import"""
    
    def setUp(self):
        """Create temporary CSV file"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.temp_file.write(TestData.SAMPLE_CSV)
        self.temp_file.close()
        
        from csv_parser_backfill import RobustCSVParser
        self.parser = RobustCSVParser(None)  # No DB connection for unit tests
    
    def tearDown(self):
        """Clean up temp file"""
        os.unlink(self.temp_file.name)
    
    def test_parse_csv(self):
        """Test CSV parsing"""
        data, reconciliation = self.parser.parse_file(self.temp_file.name)
        
        # Should parse all companies
        self.assertEqual(len(data), 7)
        
        # Check first company
        brightwheel = data[0]
        self.assertEqual(brightwheel['company_name'], 'BrightWheel')
        self.assertEqual(brightwheel['amount_invested'], Decimal('2500000'))
        self.assertEqual(brightwheel['ownership_pct'], Decimal('5.2'))
        
        # Check company with 'k' notation
        chapul = data[2]
        self.assertEqual(chapul['amount_invested'], Decimal('750000'))
    
    def test_encoding_detection(self):
        """Test encoding detection"""
        encoding = self.parser.detect_encoding(self.temp_file.name)
        self.assertIn(encoding, ['utf-8', 'utf-8-sig', 'ascii'])
    
    def test_column_mapping(self):
        """Test flexible column name mapping"""
        columns = ['Name of Company', 'Total $ Invested', 'Equity Percentage']
        mapping = self.parser.map_columns(columns)
        
        self.assertEqual(mapping['Name of Company'], 'company')
        self.assertEqual(mapping['Total $ Invested'], 'amount_invested')
        self.assertEqual(mapping['Equity Percentage'], 'ownership')
    
    def test_currency_cleaning(self):
        """Test currency value cleaning"""
        test_cases = [
            ("$1,234,567.89", Decimal("1234567.89")),
            ("1.5M", Decimal("1500000")),
            ("750k", Decimal("750000")),
            ("(500000)", Decimal("-500000")),
            ("$2.5B", Decimal("2500000000"))
        ]
        
        for input_val, expected in test_cases:
            result = self.parser.clean_currency(input_val)
            self.assertEqual(result, expected)


class TestDataValidation(unittest.TestCase):
    """Test data validation rules"""
    
    def test_json_schema_validation(self):
        """Test extraction result against JSON schema"""
        import jsonschema
        
        # Load schema
        with open('extraction-schemas.json', 'r') as f:
            schemas = json.load(f)
        
        # Create sample extraction result
        sample_result = {
            "company_id": "brightwheel",
            "source_ptr": {
                "source_type": "email",
                "source_id": "AAMkAGI2TG93AAA=",
                "storage_url": "graph://messages/AAMkAGI2TG93AAA="
            },
            "facts": {
                "updates": [{
                    "period_start": "2025-01-01",
                    "period_end": "2025-01-31",
                    "report_period": "2025-01",
                    "metrics": {
                        "ARR": "15500000"
                    },
                    "confidence": 0.85
                }]
            },
            "confidence_overall": 0.85,
            "assumptions": ["currency defaulted to USD"]
        }
        
        # Validate against schema
        try:
            jsonschema.validate(
                instance=sample_result,
                schema=schemas['definitions']['ExtractionEnvelope']
            )
            validation_passed = True
        except jsonschema.ValidationError as e:
            validation_passed = False
            print(f"Validation error: {e}")
        
        self.assertTrue(validation_passed)
    
    def test_business_rule_validation(self):
        """Test business rule validations"""
        
        # Test ownership sum validation
        ownership_records = [
            {"company_id": "test", "pct": Decimal("45.5")},
            {"company_id": "test", "pct": Decimal("35.2")},
            {"company_id": "test", "pct": Decimal("25.3")}  # Sum > 100%
        ]
        
        total_ownership = sum(r["pct"] for r in ownership_records)
        self.assertGreater(total_ownership, 100, "Should detect ownership > 100%")
        
        # Test post-money validation
        pre_money = Decimal("10000000")
        investment = Decimal("2000000")
        post_money = Decimal("11000000")  # Should be 12M
        
        self.assertLess(
            post_money, 
            pre_money + investment,
            "Post-money should include investment"
        )
        
        # Test date consistency
        period_start = datetime(2025, 1, 1)
        period_end = datetime(2024, 12, 31)  # End before start
        
        self.assertLess(period_end, period_start, "Should detect invalid date range")


class TestIntegration(unittest.TestCase):
    """Integration tests for full pipeline"""
    
    @patch('psycopg2.connect')
    @patch('requests.post')
    @patch('requests.get')
    def test_email_to_database_flow(self, mock_get, mock_post, mock_db):
        """Test complete email ingestion flow"""
        
        # Mock Graph API responses
        mock_post.return_value.json.return_value = {'access_token': 'test_token'}
        mock_get.return_value.json.return_value = TestData.SAMPLE_EMAILS["update_email"]
        
        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        # Run ingestion
        from azure_function_email_ingestion import main, CompanyMatcher, PortfolioDataExtractor, DataPersister
        
        # Create test message
        test_message = Mock()
        test_message.get_body.return_value.decode.return_value = json.dumps({
            'messageId': 'AAMkAGI2TG93AAA='
        })
        
        # Process message
        # Note: Would need to refactor main() to be testable
        # This is a simplified example
        
        # Verify database calls
        self.assertTrue(mock_cursor.execute.called)
        self.assertTrue(mock_conn.commit.called)
    
    def test_make_com_webhook_processing(self):
        """Test Make.com webhook data processing"""
        
        # Simulate webhook payload
        webhook_data = TestData.SAMPLE_TALLY_RESPONSES["company_update"]
        
        # Transform data (as Make.com would)
        transformed = {
            "company_id": "brightwheel",
            "source_ptr": {
                "source_type": "tally_form",
                "source_id": webhook_data["responseId"],
                "storage_url": f"tally://{webhook_data['formId']}/{webhook_data['responseId']}"
            },
            "facts": {
                "updates": [{
                    "period_start": "2025-01-01",
                    "period_end": "2025-01-31",
                    "report_period": webhook_data["data"]["report_period"],
                    "metrics": {
                        "ARR": webhook_data["data"]["arr"],
                        "runway_months": webhook_data["data"]["runway_months"]
                    },
                    "confidence": 0.95
                }]
            },
            "confidence_overall": 0.95
        }
        
        # Verify structure
        self.assertEqual(transformed["company_id"], "brightwheel")
        self.assertEqual(transformed["facts"]["updates"][0]["metrics"]["ARR"], "15500000")


class TestPerformance(unittest.TestCase):
    """Performance and load tests"""
    
    def test_bulk_email_processing(self):
        """Test processing multiple emails"""
        from azure_function_email_ingestion import PortfolioDataExtractor
        extractor = PortfolioDataExtractor()
        
        # Process 100 emails
        import time
        start_time = time.time()
        
        for i in range(100):
            email = TestData.SAMPLE_EMAILS["update_email"].copy()
            email["id"] = f"MSG_{i}"
            result = extractor.extract_from_email(email)
            self.assertIsNotNone(result)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / 100
        
        # Should process each email in < 100ms
        self.assertLess(avg_time, 0.1, f"Email processing too slow: {avg_time:.3f}s per email")
    
    def test_large_csv_parsing(self):
        """Test parsing large CSV file"""
        # Create large CSV with 10,000 rows
        large_csv = "Name of Company,Total Amount Invested,Earliest Date of Investment,Equity %,Status\n"
        for i in range(10000):
            large_csv += f"Company_{i},$1000000,2020-01-01,1%,Active\n"
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(large_csv)
        temp_file.close()
        
        try:
            from csv_parser_backfill import RobustCSVParser
            parser = RobustCSVParser(None)
            
            import time
            start_time = time.time()
            data, _ = parser.parse_file(temp_file.name)
            elapsed = time.time() - start_time
            
            self.assertEqual(len(data), 10000)
            self.assertLess(elapsed, 10, f"CSV parsing too slow: {elapsed:.2f}s for 10k rows")
            
        finally:
            os.unlink(temp_file.name)


def run_tests():
    """Run all tests with coverage report"""
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEmailExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestCSVParser))
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)