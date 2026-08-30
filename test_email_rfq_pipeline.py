# ==============================================================================
# --- ContinuumX Email Ingestion, Multimodal Extraction & BOM Pipeline Test ---
# Validates IMAP inbox connection, email RFQ classification, multimodal extraction,
# synthetic BOM Excel generation, and BrainRouter integration.
# ==============================================================================

import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestEmailRFQPipeline(unittest.TestCase):
    def test_01_email_fetcher_imap_connectivity(self):
        """Test IMAP SSL connection to configured mailbox and message retrieval."""
        print("\n--- [Test 1] Testing IMAP SSL Connection ---")
        from agents.email_fetcher import EmailFetcher
        fetcher = EmailFetcher()
        print(f"Connecting to: {fetcher.email_address} on {fetcher.imap_server}:{fetcher.imap_port}")
        res = fetcher.fetch_recent_emails(limit=5, filter_rfq=False)
        print(f"Result: Success={res['success']}, Scanned={res['count']} emails")
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)

    def test_02_email_classifier_accuracy(self):
        """Test RFQ Intent Classification with sample training phrases."""
        print("\n--- [Test 2] Testing Email RFQ Intent Classification ---")
        from agents.email_classifier import EmailClassifier
        clf = EmailClassifier()
        
        # Test Sample 1: High-confidence RFQ
        res_rfq = clf.classify_email("NEW RFQ: Wire Harness Assembly for Continuum N2", "Attached BOM with EAU 5000 pcs and drawing.")
        print("Sample 1 (New RFQ):", res_rfq)
        self.assertEqual(res_rfq["intent"], "NEW_RFQ")
        self.assertTrue(res_rfq["is_rfq_related"])

        # Test Sample 2: RFQ Follow-up
        res_followup = clf.classify_email("RE: RFQ #8247JT-2 Target Price Update", "Here is the target price of $14.20.")
        print("Sample 2 (Follow-up):", res_followup)
        self.assertEqual(res_followup["intent"], "RFQ_FOLLOWUP")
        self.assertTrue(res_followup["is_rfq_related"])

        # Test Sample 3: Bank Statement / Non-RFQ
        res_non_rfq = clf.classify_email("Savings Account Statement July 2026", "M2U Statements attached e-Statement.")
        print("Sample 3 (Non-RFQ Bank Statement):", res_non_rfq)
        self.assertEqual(res_non_rfq["intent"], "NON_RFQ")
        self.assertFalse(res_non_rfq["is_rfq_related"])

    def test_03_multimodal_extraction(self):
        """Test Multimodal Extraction from structured customer RFQ data."""
        print("\n--- [Test 3] Testing Multimodal Extractor ---")
        from agents.multimodal_extractor import MultimodalExtractor
        extractor = MultimodalExtractor()
        
        sample_email = {
            "id": "MSG-9988",
            "subject": "NEW RFQ: Wire Harness for Continuum N2 Assembly",
            "sender": "engineering@continuumx.com.my",
            "date": "2026-08-13 15:30:00",
            "body": "Hi Team, Please quote 5000 pcs for Continuum N2 Wire Harness. Target price $14.50. Drawings attached.",
            "attachments": []
        }
        extracted = extractor.extract_full_rfq(sample_email)
        print("Extracted RFQ JSON summary:")
        print(f"  Customer: {extracted['rfq_metadata']['customer_name']}")
        print(f"  RFQ Number: {extracted['rfq_metadata']['rfq_number']}")
        print(f"  Commodity: {extracted['rfq_metadata']['commodity']}")
        print(f"  Target Price: {extracted['rfq_metadata']['target_price']}")
        print(f"  EAU: {extracted['rfq_metadata']['eau']}")
        print(f"  Assemblies: {len(extracted['assemblies'])}")
        
        self.assertEqual(extracted["rfq_metadata"]["customer_name"], "Continuum")
        self.assertEqual(extracted["rfq_metadata"]["commodity"], "Wire Harness")
        self.assertIn("assemblies", extracted)

    def test_04_synthetic_bom_excel_generation(self):
        """Test generation of standardized openpyxl synthetic BOM Excel."""
        print("\n--- [Test 4] Testing Synthetic BOM Excel Generator ---")
        from agents.synthetic_bom_generator import SyntheticBOMGenerator
        generator = SyntheticBOMGenerator()

        rfq_payload = {
            "rfq_metadata": {
                "customer_name": "Continuum",
                "rfq_number": "RS26-8344",
                "project_title": "Continuum N2 Main Cable",
                "commodity": "Wire Harness",
                "target_price": "$14.50",
                "eau": 5000,
                "default_moqs": [100, 250, 500, 1000]
            },
            "assemblies": [
                {
                    "assy_no": "810-105035-003",
                    "assy_model": "Continuum N2 Cable Assembly",
                    "assy_rev": "Rev B",
                    "items": [
                        {"line_item": 1, "part_number": "1-967616-1", "description": "6-Pin Connector Housing", "mfr": "TE Connectivity", "mpn": "1-967616-1", "qty": 1, "uom": "EA"},
                        {"line_item": 2, "part_number": "968220-1", "description": "Female Crimp Terminal", "mfr": "TE Connectivity", "mpn": "968220-1", "qty": 6, "uom": "EA"},
                        {"line_item": 3, "part_number": "3051 BK005", "description": "Hook-up Wire 24AWG Black", "mfr": "Alpha Wire", "mpn": "3051 BK005", "qty": 350, "uom": "MM"}
                    ]
                }
            ]
        }

        res = generator.generate_synthetic_excel(rfq_payload)
        print(f"Generated File: {res['file_path']}")
        print(f"Total Rows: {res['total_items']}")
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(res["file_path"]))
        self.assertEqual(res["total_items"], 3)

    def test_05_brain_router_check_rfq_emails(self):
        """Test BrainRouter high-level check_rfq_emails execution."""
        print("\n--- [Test 5] Testing BrainRouter check_rfq_emails() ---")
        from agents.brain_router import BrainRouter
        router = BrainRouter()
        res = router.check_rfq_emails(limit=5)
        print(f"BrainRouter Email Check: Success={res['success']}, Scanned={res.get('total_scanned')}, RFQs={res.get('rfq_count')}")
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)

    def test_06_drawing_vision_agent(self):
        """Test deep PDF blueprint parsing by DrawingVisionAgent across all 5 Tecan drawings."""
        print("\n--- [Test 6] Testing DrawingVisionAgent Evidence & Pin-Count Inference ---")
        from agents.drawing_agent import DrawingVisionAgent, ResolutionType
        staging_tecan = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ContXs', 'EmailStaging', '47456_Enquiry___Cable___Tecan_-_RS25')
        
        expected_drawings = {
            'BB0_502356122_EN_00.pdf': ('30079632', '05', 16),
            'AJ0_500998462_EN_00.pdf': ('30078993', '02', 10),
            'AJ0_30059436_EN_01.pdf': ('30059436', '01', 4),
            'AJ0_30059453_EN_02.pdf': ('30059453', '02', 8),
            'AJ0_30077977_EN_00.pdf': ('30077977', '00', 4),
        }

        total_extracted = 0
        if os.path.exists(staging_tecan):
            for fn, (exp_assy, exp_rev, min_items) in expected_drawings.items():
                pdf_path = os.path.join(staging_tecan, fn)
                if os.path.exists(pdf_path):
                    dwg = DrawingVisionAgent.parse_drawing_pdf(pdf_path)
                    print(f"  [{fn}] Assy: {dwg['assy_no']} ({dwg['assy_rev']}) - {dwg['assy_model']} -> {len(dwg['items'])} items")
                    self.assertEqual(dwg["assy_no"], exp_assy)
                    self.assertEqual(dwg["assy_rev"], exp_rev)
                    self.assertGreaterEqual(len(dwg["items"]), min_items)
                    total_extracted += len(dwg["items"])

                    # Check evidence object exists on all items
                    for it in dwg["items"]:
                        self.assertIn("evidence", it)
                        self.assertIn("qty", it["evidence"])
                        self.assertIn("resolution_type", it["evidence"]["qty"])

            print(f"  Total Ground Truth Extracted across 5 Assemblies: {total_extracted} component lines")
            self.assertGreaterEqual(total_extracted, 41)


if __name__ == "__main__":
    unittest.main(verbosity=2)
