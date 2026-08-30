# ==============================================================================
# --- ContinuumX Intelligent Email Fetcher & Ingestion Engine ---
# Connects to Gmail / IMAP mailboxes in the background, extracts RFQ emails,
# downloads multi-format attachments (PDFs, drawings, Excel), and runs classification.
# ==============================================================================

import os
import sys
import re
import json
import imaplib
import email
from email.header import decode_header
import configparser
from datetime import datetime

# Standardized Base Directory Resolution Pattern
if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    BASE_DIR = os.getcwd()

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class EmailFetcher:
    """
    Headless background email fetcher using IMAP SSL.
    Retrieves incoming emails, extracts bodies & attachments, and runs RFQ classification.
    """
    def __init__(self, config_path=None):
        if not config_path:
            config_path = os.path.join(BASE_DIR, "config.ini")

        self.config_path = config_path
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.email_address = "aitinkteng03@gmail.com"
        self.email_password = ""
        self.staging_dir = self._get_staging_dir()

        self._load_config()
        
        # Initialize Email Classifier
        try:
            from agents.email_classifier import EmailClassifier
            self.classifier = EmailClassifier()
        except Exception as e:
            print(f"[EmailFetcher] Classifier notice: {e}")
            self.classifier = None

    def _get_staging_dir(self):
        """Resolves local app data staging directory for email attachments."""
        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', os.path.join(BASE_DIR, 'data')))
        staging = os.path.join(local_appdata, "ContXs", "EmailStaging")
        os.makedirs(staging, exist_ok=True)
        return staging

    def _load_config(self):
        """Loads IMAP or SMTP credentials dynamically from config.ini."""
        if not os.path.exists(self.config_path):
            return

        try:
            cfg = configparser.ConfigParser()
            cfg.read(self.config_path, encoding='utf-8')

            # 1. Check explicit [IMAP] section
            if 'IMAP' in cfg:
                self.imap_server = cfg['IMAP'].get('imap_server', self.imap_server).strip()
                self.imap_port = int(cfg['IMAP'].get('imap_port', str(self.imap_port)).strip())
                self.email_address = cfg['IMAP'].get('email_address', self.email_address).strip()
                self.email_password = cfg['IMAP'].get('email_password', '').strip()

            # 2. Fallback to [SMTP] section if IMAP password not specified
            if not self.email_password and 'SMTP' in cfg:
                self.email_address = cfg['SMTP'].get('sender_email', self.email_address).strip()
                self.email_password = cfg['SMTP'].get('sender_password', '').strip()

        except Exception as e:
            print(f"[EmailFetcher] Config load warning: {e}")

    @staticmethod
    def _decode_str(header_val):
        """Safely decodes email MIME headers to unicode string."""
        if not header_val:
            return ""
        decoded_fragments = decode_header(header_val)
        result = []
        for frag, charset in decoded_fragments:
            if isinstance(frag, bytes):
                try:
                    result.append(frag.decode(charset or 'utf-8', errors='replace'))
                except Exception:
                    result.append(frag.decode('latin1', errors='replace'))
            else:
                result.append(str(frag))
        return "".join(result).strip()

    @staticmethod
    def _convert_html_tables_to_grid(html_content):
        """Universally converts any HTML <table> in email HTML into aligned Unicode box grid tables."""
        if not html_content or "<table" not in html_content.lower():
            return html_content

        def _replace_table(match):
            tbl_html = match.group(0)
            try:
                rows = []
                tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl_html, flags=re.DOTALL | re.IGNORECASE)
                for tr in tr_matches:
                    cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', tr, flags=re.DOTALL | re.IGNORECASE)
                    clean_cells = []
                    for c in cells:
                        c_text = re.sub(r'<[^>]+>', ' ', c)
                        c_text = re.sub(r'&nbsp;', ' ', c_text)
                        c_text = re.sub(r'&amp;', '&', c_text)
                        c_text = re.sub(r'&lt;', '<', c_text)
                        c_text = re.sub(r'&gt;', '>', c_text)
                        c_text = re.sub(r'\s+', ' ', c_text).strip()
                        clean_cells.append(c_text)
                    if any(clean_cells):
                        rows.append(clean_cells)
                if not rows:
                    return ""
                max_cols = max(len(r) for r in rows)
                for r in rows:
                    while len(r) < max_cols:
                        r.append("")
                widths = [max(len(r[i]) for r in rows) for i in range(max_cols)]
                widths = [max(w, 4) for w in widths]

                def sep(left, mid, right, fill="─"):
                    return left + mid.join(fill * (w + 2) for w in widths) + right

                top, mid, bot = sep("┌", "┬", "┐"), sep("├", "┼", "┤"), sep("└", "┴", "┘")
                lines = [top]
                for idx, r in enumerate(rows):
                    row_str = "│ " + " │ ".join(f"{r[i]:<{widths[i]}}" for i in range(max_cols)) + " │"
                    lines.append(row_str)
                    if idx == 0 and len(rows) > 1:
                        lines.append(mid)
                lines.append(bot)
                return "\n" + "\n".join(lines) + "\n"
            except Exception:
                return tbl_html

        return re.sub(r'<table[^>]*>.*?</table>', _replace_table, html_content, flags=re.DOTALL | re.IGNORECASE)

    @staticmethod
    def _clean_html_to_text(html_content):
        """Converts raw HTML email body into clean readable text with preserved table grids."""
        text = re.sub(r'<style.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = EmailFetcher._convert_html_tables_to_grid(text)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def fetch_recent_emails(self, limit=35, unread_only=False, filter_rfq=False):
        """
        Connects to Gmail / IMAP server using high-performance 2-Stage Header Peeking.
        Scans recent emails, identifies RFQs, downloads attachments, and runs classification.
        """
        if not self.email_address or not self.email_password:
            return {
                "success": False,
                "email_address": self.email_address,
                "count": 0,
                "rfq_count": 0,
                "emails": [],
                "error": "Email address or App Password missing in config.ini ([SMTP] or [IMAP] section)."
            }

        mail = None
        try:
            # 1. Connect via SSL
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            mail.select("INBOX")

            # 2. Search for message IDs
            search_crit = "UNSEEN" if unread_only else "ALL"
            status, data = mail.search(None, search_crit)
            if status != "OK" or not data[0]:
                return {
                    "success": True,
                    "email_address": self.email_address,
                    "count": 0,
                    "rfq_count": 0,
                    "emails": [],
                    "error": None
                }

            msg_ids = data[0].split()
            # Fetch latest candidates
            candidate_ids = msg_ids[-limit:]
            candidate_ids.reverse()

            # 3. Stage 1: Fast Header Peeking to identify RFQ candidates
            header_items = []
            for m_id in candidate_ids:
                try:
                    res_code, h_data = mail.fetch(m_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                    if res_code == "OK" and h_data and h_data[0]:
                        raw_h = h_data[0][1]
                        h_msg = email.message_from_bytes(raw_h)
                        subj = self._decode_str(h_msg.get("Subject", "No Subject"))
                        snd = self._decode_str(h_msg.get("From", "Unknown Sender"))
                        dt = self._decode_str(h_msg.get("Date", ""))
                        
                        # Check classification on header
                        # Check classification on header
                        clf_res = {"intent": "NON_RFQ", "confidence": 0.5, "is_rfq_related": False, "matched_keywords": []}
                        if self.classifier:
                            clf_res = self.classifier.classify_email(subj, f"From: {snd}", sender=snd)

                        is_likely_rfq = clf_res["is_rfq_related"]

                        header_items.append({
                            "id": m_id,
                            "subject": subj,
                            "sender": snd,
                            "date": dt,
                            "classification": clf_res,
                            "is_likely_rfq": is_likely_rfq
                        })
                except Exception as e:
                    print(f"[EmailFetcher] Header peek warning for {m_id}: {e}")

            # 4. Stage 2: Download Full Body and Attachments ONLY for candidate RFQs
            parsed_emails = []

            for h_item in header_items:
                m_id = h_item["id"]
                msg_uid = m_id.decode() if isinstance(m_id, bytes) else str(m_id)
                subj = h_item["subject"]
                snd = h_item["sender"]
                dt = h_item["date"]
                clf = h_item["classification"]
                is_rfq = h_item["is_likely_rfq"]

                # If filtering for RFQs only and item is definitely non-rfq, skip
                if filter_rfq and not is_rfq:
                    continue

                body_plain = ""
                body_html = ""
                attachments = []
                email_stage_dir = ""

                # Only download full RFC822 and attachments if it's an RFQ candidate!
                if is_rfq:
                    safe_subj = re.sub(r'[^a-zA-Z0-9_-]', '_', subj)[:30]
                    email_stage_dir = os.path.join(self.staging_dir, f"{msg_uid}_{safe_subj}")
                    os.makedirs(email_stage_dir, exist_ok=True)

                    # Check if attachments and body are already cached on disk
                    existing_files = [f for f in os.listdir(email_stage_dir) if not f.startswith('unzipped_') and os.path.isfile(os.path.join(email_stage_dir, f))]
                    if existing_files:
                        for ef in existing_files:
                            ef_path = os.path.join(email_stage_dir, ef)
                            attachments.append({
                                "filename": ef,
                                "path": ef_path,
                                "content_type": "application/octet-stream",
                                "size_bytes": os.path.getsize(ef_path)
                            })
                        body_cache_file = os.path.join(email_stage_dir, "_body.txt")
                        if os.path.exists(body_cache_file):
                            try:
                                with open(body_cache_file, "r", encoding="utf-8", errors="replace") as bf:
                                    body_plain = bf.read()
                            except Exception:
                                pass

                    # If not cached on disk, fetch from IMAP
                    if not attachments:
                        try:
                            status, fetch_data = mail.fetch(m_id, "(RFC822)")
                            if status == "OK" and fetch_data and fetch_data[0]:
                                raw_email = fetch_data[0][1]
                                full_msg = email.message_from_bytes(raw_email)

                                if full_msg.is_multipart():
                                    for part in full_msg.walk():
                                        content_type = part.get_content_type()
                                        content_disp = str(part.get("Content-Disposition", ""))

                                        if "attachment" in content_disp or part.get_filename():
                                            fn = self._decode_str(part.get_filename() or f"attachment_{len(attachments)+1}")
                                            safe_fn = os.path.basename(fn)
                                            file_data = part.get_payload(decode=True)
                                            if file_data:
                                                target_path = os.path.join(email_stage_dir, safe_fn)
                                                with open(target_path, "wb") as f_out:
                                                    f_out.write(file_data)
                                                attachments.append({
                                                    "filename": safe_fn,
                                                    "path": target_path,
                                                    "content_type": content_type,
                                                    "size_bytes": len(file_data)
                                                })
                                        elif content_type == "text/plain" and not body_plain:
                                            payload = part.get_payload(decode=True)
                                            if payload:
                                                body_plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                        elif content_type == "text/html" and not body_html:
                                            payload = part.get_payload(decode=True)
                                            if payload:
                                                body_html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                else:
                                    payload = full_msg.get_payload(decode=True)
                                    if payload:
                                        body_plain = payload.decode(full_msg.get_content_charset() or "utf-8", errors="replace")

                                # Cache plain body & HTML body to disk for instant offline re-parsing
                                if body_plain:
                                    try:
                                        with open(os.path.join(email_stage_dir, "_body.txt"), "w", encoding="utf-8", errors="replace") as bf:
                                            bf.write(body_plain)
                                    except Exception:
                                        pass
                                if body_html:
                                    try:
                                        with open(os.path.join(email_stage_dir, "_body.html"), "w", encoding="utf-8", errors="replace") as hf:
                                            hf.write(body_html)
                                    except Exception:
                                        pass
                        except Exception as e:
                            print(f"[EmailFetcher] Body fetch error for {m_id}: {e}")

                final_body = body_plain.strip() if body_plain else (self._clean_html_to_text(body_html) if body_html else "")

                # Final classification check
                if is_rfq:
                    clf["intent"] = "NEW_RFQ" if clf["intent"] != "RFQ_FOLLOWUP" else clf["intent"]
                    clf["is_rfq_related"] = True
                    clf["confidence"] = max(clf.get("confidence", 0.85), 0.90)

                email_obj = {
                    "id": msg_uid,
                    "subject": subj,
                    "sender": snd,
                    "date": dt,
                    "body": final_body,
                    "body_html": body_html,
                    "attachments": attachments,
                    "classification": clf,
                    "stage_dir": email_stage_dir
                }
                parsed_emails.append(email_obj)

            # Consolidate emails in the same conversation thread (same normalized subject)
            consolidated = {}
            for e in parsed_emails:
                raw_s = e["subject"]
                s_clean = re.sub(r'^(?:\[(?:re|fwd|fw)\]|\((?:re|fwd|fw)\)|(?:re|fwd|fya|fw)[\s:_-]+)+', '', raw_s, flags=re.I)
                s_clean = re.sub(r'\[.*?\]', '', s_clean)
                norm_subj = re.sub(r'\s+', ' ', s_clean).strip().lower()
                if not norm_subj:
                    norm_subj = raw_s.strip().lower()

                if norm_subj not in consolidated:
                    consolidated[norm_subj] = e
                else:
                    existing = consolidated[norm_subj]
                    existing_fps = set(a.get("filename") for a in existing["attachments"] if isinstance(a, dict))
                    for att in e["attachments"]:
                        att_fn = att.get("filename") if isinstance(att, dict) else os.path.basename(str(att))
                        if att_fn not in existing_fps:
                            existing["attachments"].append(att)
                            existing_fps.add(att_fn)
                    if e.get("body") and e["body"] not in existing["body"]:
                        existing["body"] = existing["body"] + "\n\n" + e["body"]

            # Merge attachments from any staging directory matching this subject thread
            for norm_subj, existing in consolidated.items():
                existing_fps = set(a.get("filename") for a in existing["attachments"] if isinstance(a, dict))
                # Extract RFQ ID code if present (e.g. '8507', '8099', '8247')
                rfq_num_m = re.search(r'\b(RS[0-9]{2}-[0-9]{3,5}|[0-9]{4,5})\b', norm_subj, re.IGNORECASE)
                target_rfq_token = rfq_num_m.group(0).lower().replace("rs25-", "").replace("rs26-", "") if rfq_num_m else ""
                
                # Tokenize normalized subject into meaningful keywords (excluding generic words)
                subj_tokens = [t for t in re.split(r'[^a-zA-Z0-9]', norm_subj.lower()) if len(t) >= 3 and t not in ('fwd', 're', 'fya', 'the', 'and', 'for', 'cable', 'rs25', 'rs26', 'tecan')]
                
                if os.path.exists(self.staging_dir):
                    for d in os.listdir(self.staging_dir):
                        d_low = d.lower()
                        # If RFQ number exists, it MUST match the directory name!
                        if target_rfq_token and target_rfq_token not in d_low:
                            continue
                        if subj_tokens and not any(t in d_low for t in subj_tokens):
                            continue
                        
                        stg_p = os.path.join(self.staging_dir, d)
                        if os.path.isdir(stg_p):
                            for f in os.listdir(stg_p):
                                if not f.startswith('unzipped_') and f != '_body.txt':
                                    f_full = os.path.join(stg_p, f)
                                    if os.path.isfile(f_full):
                                        repaired = False
                                        for att_item in existing["attachments"]:
                                            if isinstance(att_item, dict) and att_item.get("filename") == f:
                                                if not os.path.exists(att_item.get("path", "")):
                                                    att_item["path"] = f_full
                                                    att_item["size_bytes"] = os.path.getsize(f_full)
                                                repaired = True
                                                break
                                        if not repaired and f not in existing_fps:
                                            existing["attachments"].append({
                                                "filename": f,
                                                "path": f_full,
                                                "size_bytes": os.path.getsize(f_full)
                                            })
                                            existing_fps.add(f)

            parsed_emails = list(consolidated.values())
            rfq_total = sum(1 for e in parsed_emails if e["classification"]["is_rfq_related"])

            return {
                "success": True,
                "email_address": self.email_address,
                "count": len(parsed_emails),
                "rfq_count": rfq_total,
                "emails": parsed_emails,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "email_address": self.email_address,
                "count": 0,
                "rfq_count": 0,
                "emails": [],
                "error": str(e)
            }
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass


if __name__ == "__main__":
    fetcher = EmailFetcher()
    print(f"Connecting to {fetcher.email_address} via IMAP...")
    res = fetcher.fetch_recent_emails(limit=30, filter_rfq=False)
    print(f"Result: Success={res['success']}, Scanned={res['count']} emails (RFQ={res['rfq_count']})")
    if res["error"]:
        print(f"Error: {res['error']}")
    for idx, em in enumerate(res["emails"], 1):
        safe_subj = em['subject'].encode('ascii', errors='replace').decode()
        safe_from = em['sender'].encode('ascii', errors='replace').decode()
        print(f"\n[{idx}] {safe_subj}")
        print(f"    From: {safe_from}")
        print(f"    Date: {em['date']}")
        print(f"    Intent: {em['classification']['intent']} (Score: {em['classification']['confidence']})")
        print(f"    Attachments: {len(em['attachments'])} file(s)")
        for att in em["attachments"]:
            safe_att = att['filename'].encode('ascii', errors='replace').decode()
            print(f"      - {safe_att} ({att['size_bytes']} bytes)")
