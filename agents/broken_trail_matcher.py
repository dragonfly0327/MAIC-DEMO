import os
import json
import re
from difflib import SequenceMatcher

class BrokenTrailMatcher:
    def __init__(self, server_path=None):
        if not server_path:
            # Fallback to load_server_path pattern
            from ref.BOM.utils import load_server_path
            server_path = load_server_path()

        self.server_path = server_path

    def extract_entities(self, text, filenames=None):
        """Extracts MPNs, RFQ numbers, and candidate customer names from email body & attachment names."""
        if filenames is None:
            filenames = []

        all_text = f"{text} {' '.join(filenames)}"
        
        # Regex patterns for Part Numbers / MPNs (e.g. 8247JT-2, 710-105035-003, GRM31CR61C475KA01L)
        mpn_pattern = r'\b[A-Z0-9]{2,5}[-\s]?[A-Z0-9]{3,8}(?:[-\s][A-Z0-9]{1,4})?\b'
        raw_mpns = re.findall(mpn_pattern, all_text)
        
        # Clean and deduplicate MPNs
        extracted_mpns = set()
        for mpn in raw_mpns:
            cleaned = mpn.strip().upper()
            if len(cleaned) >= 5 and not cleaned.startswith(("EMAIL", "ATTACH", "GMAIL", "HTTP")):
                extracted_mpns.add(cleaned)

        # Regex for RFQ ID format (e.g. RS26-8305, RFQ-1002, RS2026-001)
        rfq_pattern = r'\b(?:RS|RFQ)[-_\s]?\d{2,4}[-_\s]?\d{3,5}\b'
        extracted_rfqs = set(re.findall(rfq_pattern, all_text, re.IGNORECASE))

        return {
            "mpns": list(extracted_mpns),
            "rfqs": [r.upper() for r in extracted_rfqs]
        }

    def match_against_active_rfqs(self, email_subject, email_body="", attachments=None):
        """
        Scans active RFQ records on the server and matches email entities
        even if the email subject or Message-ID trail was broken.
        """
        entities = self.extract_entities(f"{email_subject} {email_body}", attachments)
        
        # Search active RFQs on server
        bom_data_dir = os.path.join(self.server_path, "BOM", "AppData", "Individual BOM Data")
        sourcing_data_dir = os.path.join(self.server_path, "Sourcing", "AppData", "Individual BOM Data")

        active_rfqs = {}
        for search_dir in [bom_data_dir, sourcing_data_dir]:
            if os.path.exists(search_dir):
                for fname in os.listdir(search_dir):
                    if fname.endswith(".json"):
                        rfq_id = fname.replace(".json", "")
                        fpath = os.path.join(search_dir, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8') as f:
                                active_rfqs[rfq_id] = json.load(f)
                        except Exception:
                            pass

        best_match = None
        highest_score = 0.0
        match_reasons = []

        full_text_upper = f"{email_subject} {email_body}".upper()

        for rfq_id, rfq_data in active_rfqs.items():
            score = 0.0
            reasons = []

            # 1. Direct RFQ ID match
            if rfq_id.upper() in full_text_upper or rfq_id.replace("-", "").upper() in full_text_upper.replace("-", ""):
                score += 0.8
                reasons.append(f"Direct RFQ ID match: {rfq_id}")

            # 2. Customer Name Fuzzy Match
            cust_name = str(rfq_data.get("customer_name") or rfq_data.get("Customer") or "").upper()
            if cust_name and len(cust_name) > 3:
                if cust_name in full_text_upper:
                    score += 0.3
                    reasons.append(f"Customer Name match: {cust_name}")

            # 3. MPN / Part Number Overlap Match
            rfq_parts = set()
            rows = rfq_data.get("rows") or rfq_data.get("items") or []
            for row in rows:
                if isinstance(row, dict):
                    mpn = str(row.get("MPN") or row.get("Part") or "").upper()
                    if mpn and len(mpn) >= 5:
                        rfq_parts.add(mpn)

            matched_parts = set(entities["mpns"]).intersection(rfq_parts)
            if matched_parts:
                part_bonus = min(0.5, len(matched_parts) * 0.25)
                score += part_bonus
                reasons.append(f"Matched Part Numbers ({len(matched_parts)}): {list(matched_parts)[:3]}")

            if score > highest_score:
                highest_score = score
                best_match = rfq_id
                match_reasons = reasons

        return {
            "matched_rfq_id": best_match if highest_score >= 0.4 else None,
            "confidence": round(min(1.0, highest_score), 4),
            "reasons": match_reasons,
            "entities_found": entities
        }

if __name__ == "__main__":
    matcher = BrokenTrailMatcher()
    res = matcher.extract_entities("RE: Revised pricing for 8247JT-2 cable assy part 710-105035-003")
    print("Extracted Entities:", res)
