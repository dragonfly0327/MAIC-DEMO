# ==============================================================================
# --- ContinuumX Intelligent Email Classifier ---
# High-precision industrial classifier with Hard Negative Exclusions for marketing/retail,
# rule-first priority for customer RFQ patterns, and TF-IDF Naive Bayes fallback.
# ==============================================================================

import os
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

HARD_NEGATIVE_SENDERS = [
    "sephora", "watsons", "mcdonald", "mcdonalds", "prudential", "maybank", "cimb",
    "rhb", "samsung", "lenovo", "airasia", "shopee", "lazada", "shein", "charleskeith",
    "charles & keith", "genting", "touch 'n go", "tngdigital", "lotus", "lotuss", "grab",
    "linkedin", "alison", "insidescoop", "glassdoor", "lhdnm", "noreply", "marketing",
    "newsletter", "promotion", "promo", "billing", "ecomm", "deals"
]

HARD_NEGATIVE_KEYWORDS = [
    "fragrance", "voucher", "voucher code", "discount code", "super kaw kaw", "birthday reward",
    "birthday bonus", "upgrade your critical illness", "savings account statement",
    "account statement", "monthly statement", "credit card statement", "turn your points",
    "cash in 10 mins", "lokal legends", "don't lose your dream car", "spicy chicken mcdeuxe",
    "redeem now", "kill switch", "peri-peri", "galaxy z fold", "drunk elephant",
    "top price drops in kuala lumpur", "fall winter 2026", "limited quantities",
    "sports edit", "i think my job is forcing me to quit", "bayaran potongan cukai",
    "order receipt from", "online store", "staycation", "points now"
]

HIGH_PRIORITY_RFQ_PATTERNS = [
    r'\brfq[-_\s#:]*([a-z0-9_-]+)',
    r'\benquiry\b',
    r'\bcable\s+(?:for\s+localization|assembly|enquiry)',
    r'\bwire\s+harness\b',
    r'\bquotation\s+request\b',
    r'\brequest\s+for\s+(?:quote|quotation)\b',
    r'\bplease\s+(?:help\s+to\s+)?quote\b',
    r'\b(?:rs25|rs26|rs24|rs27)[-_][0-9]{4,5}\b',
    r'\battached\s+(?:drawing|bom|specification|rfq)\b',
    r'\bannual\s+consumption\s*\(eau\)',
    r'\btarget\s+price\b'
]


class EmailClassifier:
    def __init__(self, dataset_path=None):
        if not dataset_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dataset_path = os.path.join(base_dir, "data", "rfq_keywords_dataset.json")

        self.dataset_path = dataset_path
        self.keywords = {}
        self.pipeline = None
        self.is_trained = False
        self._initialize_and_train()

    def _initialize_and_train(self):
        """Loads dataset and trains local TF-IDF Naive Bayes classifier."""
        if not os.path.exists(self.dataset_path):
            return

        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.keywords = data.get("keywords", {})
            training_samples = data.get("training_samples", [])

            if training_samples:
                texts = [s["text"] for s in training_samples]
                labels = [s["label"] for s in training_samples]

                self.pipeline = Pipeline([
                    ('tfidf', TfidfVectorizer(ngram_range=(1, 2), stop_words='english')),
                    ('clf', MultinomialNB(alpha=0.1))
                ])

                self.pipeline.fit(texts, labels)
                self.is_trained = True
        except Exception as e:
            print(f"[EmailClassifier] Training warning: {e}")

    def classify_email(self, email_subject, email_body="", sender=""):
        """
        Classifies incoming email into [NEW_RFQ], [RFQ_FOLLOWUP], or [NON_RFQ].
        Applies Hard Negative Exclusions, High-Priority RFQ regex matching, and ML scoring.
        """
        subject = str(email_subject or "").strip()
        body = str(email_body or "").strip()
        sender_str = str(sender or "").lower()
        full_text = f"{subject} {body} {sender_str}".strip()
        full_lower = full_text.lower()
        subject_lower = subject.lower()

        # -------------------------------------------------------------
        # 1. HARD NEGATIVE EXCLUSION RULES (100% Guaranteed Filter)
        # -------------------------------------------------------------
        # Exclude system's own dispatch / revert notifications
        if subject_lower.startswith("[continuumx]") or "continuumx system" in sender_str:
            return {
                "intent": "NON_RFQ",
                "confidence": 0.99,
                "matched_keywords": ["system_dispatch_notification"],
                "is_rfq_related": False
            }

        # Check sender domain / brand exclusions
        for bad_sender in HARD_NEGATIVE_SENDERS:
            if bad_sender in sender_str or bad_sender in subject_lower:
                # Unless explicitly containing an active RFQ ID pattern from a customer
                if not re.search(r'\b(?:rs25|rs26)[-_][0-9]{4}\b', subject_lower):
                    return {
                        "intent": "NON_RFQ",
                        "confidence": 0.99,
                        "matched_keywords": [bad_sender],
                        "is_rfq_related": False
                    }

        # Check keyword exclusions in subject
        for bad_kw in HARD_NEGATIVE_KEYWORDS:
            if bad_kw in subject_lower:
                return {
                    "intent": "NON_RFQ",
                    "confidence": 0.98,
                    "matched_keywords": [bad_kw],
                    "is_rfq_related": False
                }

        # -------------------------------------------------------------
        # 2. HIGH-PRIORITY RFQ REGEX MATCHING (Rule-First Priority)
        # -------------------------------------------------------------
        matched_rfq_rules = []
        for pattern in HIGH_PRIORITY_RFQ_PATTERNS:
            m = re.search(pattern, subject_lower, re.IGNORECASE)
            if not m:
                m = re.search(pattern, full_lower[:1000], re.IGNORECASE)
            if m:
                matched_rfq_rules.append(m.group(0))

        # Check thread markers for follow-up
        if subject_lower.startswith(("re:", "fwd:", "fw:")):
            if matched_rfq_rules or "target price" in full_lower or "eau" in full_lower:
                return {
                    "intent": "RFQ_FOLLOWUP",
                    "confidence": 0.95,
                    "matched_keywords": matched_rfq_rules or ["re: rfq"],
                    "is_rfq_related": True
                }

        if matched_rfq_rules:
            return {
                "intent": "NEW_RFQ",
                "confidence": 0.95,
                "matched_keywords": matched_rfq_rules,
                "is_rfq_related": True
            }

        # -------------------------------------------------------------
        # 3. TF-IDF MACHINE LEARNING PREDICTION
        # -------------------------------------------------------------
        predicted_label = "NON_RFQ"
        confidence = 0.5

        if self.is_trained and self.pipeline:
            try:
                probs = self.pipeline.predict_proba([f"{subject} {body[:500]}"])[0]
                classes = list(self.pipeline.classes_)
                max_idx = probs.argmax()
                predicted_label = classes[max_idx]
                confidence = float(probs[max_idx])
            except Exception as ex:
                print(f"[EmailClassifier] ML error: {ex}")

        # Conservative threshold: ML alone needs > 0.85 confidence to trigger RFQ
        is_rfq = predicted_label in ("NEW_RFQ", "RFQ_FOLLOWUP") and confidence >= 0.85

        return {
            "intent": predicted_label if is_rfq else "NON_RFQ",
            "confidence": round(confidence, 4),
            "matched_keywords": matched_rfq_rules,
            "is_rfq_related": is_rfq
        }


if __name__ == "__main__":
    clf = EmailClassifier()
    # Test 1: Sephora (Must be NON_RFQ)
    t1 = clf.classify_email("Just dropped: Rare Beauty's New Fragrance 🌸", sender="hello@beauty.sephora.my")
    print("Test 1 (Sephora):", t1["intent"], "is_rfq:", t1["is_rfq_related"])

    # Test 2: Jessie Kong (Must be NEW_RFQ)
    t2 = clf.classify_email("RFQ - Eastek/Graco - RS26-8004", "Please help to quote. End Customer: Graco. EAU 3-5k", sender="jessiekong@radysis-asia.com")
    print("Test 2 (Graco RFQ):", t2["intent"], "is_rfq:", t2["is_rfq_related"])

    # Test 3: Jessie Kong Cable Enquiry (Must be NEW_RFQ)
    t3 = clf.classify_email("Enquiry ~ Cable _ Tecan - RS25-8099", "Here is enquiry from Tecan.", sender="jessiekong@radysis-asia.com")
    print("Test 3 (Tecan Cable Enquiry):", t3["intent"], "is_rfq:", t3["is_rfq_related"])
