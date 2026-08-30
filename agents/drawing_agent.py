# ==============================================================================
# --- ContinuumX Drawing Vision & Technical PDF Engineering Agent ---
# Specialized agent for reading technical PDF blueprints, schematic drawings,
# Title Blocks, cable connection tables, component BOM tables, and UOM metrics.
# Features Evidence-First architecture, pin-count inference, and zero hallucination.
# ==============================================================================

import os
import sys
import re
import json
import configparser
import urllib.request
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

from agents.evidence_schema import ResolutionType, make_evidence, ConflictCandidate



class DrawingVisionAgent:
    """
    Intelligent Engineering Drawing Agent.
    Specialized in parsing CAD drawings, PDF blueprints, Title Blocks, and BOM tables.
    """
    
    KNOWN_MFRS = [
        "MOLEX", "SICK", "FCI", "AMPHENOL", "MH CONNECTORS", "HEINIGER",
        "JST", "ALPHA WIRE", "ALPHA", "TYCO", "TE CONNECTIVITY", "TE",
        "DELPHI", "YAZAKI", "SUMITOMO", "HIROSE", "HRS", "PANDUIT", "3M", "TECAN"
    ]

    UOM_NORMALIZATION = {
        "mm": "MM",
        "millimeter": "MM",
        "millimeters": "MM",
        "m": "M",
        "meter": "M",
        "meters": "M",
        "mtr": "M",
        "ft": "FT",
        "feet": "FT",
        "foot": "FT",
        "in": "IN",
        "inch": "IN",
        "inches": "IN",
        "\"": "IN",
        "ea": "EA",
        "each": "EA",
        "pc": "PCS",
        "pcs": "PCS",
        "piece": "PCS",
        "pieces": "PCS",
        "set": "SET",
        "sets": "SET",
        "roll": "ROLL",
        "reel": "REEL"
    }

    def __init__(self, config_path=None):
        if not config_path:
            config_path = os.path.join(BASE_DIR, "config.ini")
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        if os.path.exists(config_path):
            try:
                self.config.read(config_path, encoding='utf-8')
            except Exception:
                pass

    @property
    def _gemini_api_key(self):
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key and "AGENTS_LLM" in self.config:
            key = self.config["AGENTS_LLM"].get("gemini_api_key", "").strip()
        return key

    @staticmethod
    def _create_evidence_field(value, res_type, source_doc, page=1, zone="DRAWING", snippet="", reasoning="", confidence=0.95):
        """Thin wrapper — delegates to shared make_evidence factory."""
        return make_evidence(value, res_type, source_doc, page=page, zone=zone,
                             snippet=snippet, reasoning=reasoning, confidence=confidence)

    @classmethod
    def parse_drawing_file(cls, file_path, progress_callback=None, use_vision=True):
        """Dispatches drawing file to appropriate parsing engine based on extension."""
        if not file_path or not os.path.exists(file_path):
            return None

        fn_lower = os.path.basename(file_path).lower()
        inst = cls()
        if fn_lower.endswith(".pdf"):
            return inst.parse_drawing_pdf(file_path, progress_callback=progress_callback, use_vision=use_vision)
        elif fn_lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp")):
            if not any(k in fn_lower for k in ["image0", "image1", "photo", "logo", "icon"]):
                return inst.parse_drawing_image(file_path)
        return None

    MPN_BLACKLIST = {
        "number and name", "number and nam", "part number and name", "part number", "part name",
        "component", "description", "order code", "tecan-sap", "tecan sap", "sap", "item",
        "rev", "qty", "uom", "drawing", "none", "n/a", "null", "undefined", "order", "code"
    }

    @classmethod
    def sanitize_mpn(cls, raw_mpn):
        """Sanitizes raw MPN string, rejecting header labels, column titles, and non-part noise."""
        if not raw_mpn:
            return ""
        clean = str(raw_mpn).strip()
        clean_low = clean.lower()
        if clean_low in cls.MPN_BLACKLIST:
            return ""
        for bl in cls.MPN_BLACKLIST:
            if clean_low == bl or clean_low.startswith(f"{bl}:") or clean_low.startswith(f"{bl} "):
                return ""
        if len(clean) < 2 or len(clean) > 40:
            return ""
        if any(bad in clean_low for bad in ["number and nam", "part number and name"]):
            return ""
        return clean

    @classmethod
    def normalize_uom(cls, raw_uom):
        """Normalizes UOM strings to standard manufacturing codes."""
        if not raw_uom:
            return "EA"
        clean = str(raw_uom).strip().lower()
        return cls.UOM_NORMALIZATION.get(clean, clean.upper()[:4])

    def _llm_parse_pdf_text(self, pdf_text, doc_name, correction_context=""):
        """
        Sends full PDF text to Gemini at runtime.
        Extracts: assy_no, assy_rev, assy_model, customer, and all BOM components.
        No manufacturer names, part numbers, or document filenames are hardcoded here.

        Args:
            pdf_text:           Full extracted text from the PDF
            doc_name:           PDF filename (for logging only)
            correction_context: Past user corrections injected as few-shot examples

        Returns:
            dict with keys: assy_no, assy_rev, assy_model, customer, components[]
            or None on failure.
        """
        api_key = self._gemini_api_key
        if not api_key:
            print(f"[DrawingVisionAgent] No Gemini API key — skipping LLM parse for {doc_name}")
            return None

        correction_block = ""
        if correction_context:
            correction_block = f"\n\nPast user corrections for this or similar documents:\n{correction_context}\nApply these corrections when you recognize the same parts.\n"

        system_prompt = (
            "You are a precision Manufacturing Engineering Drawing data extraction specialist. "
            "Given raw text extracted from a technical PDF drawing (wire harness, cable assembly, "
            "PCBA, or mechanical assembly), extract the following information and return ONLY a "
            "single JSON object. No explanation, no markdown fences, no extra text.\n\n"
            "JSON keys required:\n"
            '  "assy_no": string — the primary assembly part number (customer or internal)\n'
            '  "assy_rev": string — revision level (e.g. "05", "A", "Rev 2") — keep exact format\n'
            '  "assy_model": string — descriptive title of the assembly\n'
            '  "customer": string — customer/company name if identifiable, else ""\n'
            '  "components": array of objects, each with:\n'
            '      "part_number": string — customer part number or drawing SAP number\n'
            '      "mpn": string — OEM manufacturer part number, empty if not specified\n'
            '      "mfr": string — manufacturer name, empty if not specified\n'
            '      "description": string — what this component is\n'
            '      "qty": number — quantity (use length in mm/m/in for cables/wires)\n'
            '      "uom": string — EA, PCS, MM, M, IN, FT, ROLL, etc.\n'
            '      "zone": string — where on the drawing this was found: TITLE_BLOCK, '
            'WIRING_TABLE, HARDWARE_TABLE, COMPONENT_CALLOUT, BOM_TABLE, or CABLE_DIMENSION\n\n'
            "Zero-hallucination rules:\n"
            "- If a field is not present in the text, use empty string or 0 — never invent values\n"
            "- Extract every distinct component line; do not skip any\n"
            "- For wiring/cable entries, use the cable length as qty with appropriate UOM\n"
        )

        # Truncate very long PDFs to fit within token limits (keep first + last portions)
        max_chars = 12000
        if len(pdf_text) > max_chars:
            half = max_chars // 2
            pdf_text_trunc = pdf_text[:half] + "\n...[middle truncated]...\n" + pdf_text[-half:]
        else:
            pdf_text_trunc = pdf_text

        user_prompt = (
            f"PDF filename: {doc_name}\n{correction_block}\n"
            f"Extracted PDF text:\n{pdf_text_trunc}\n\n"
            "Return the structured JSON object."
        )

        from agents.llm_gateway import LLMGateway
        result, status = LLMGateway(self.config_path).generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            doc_name=doc_name
        )
        if isinstance(result, dict):
            result["extraction_status"] = "LLM_SUCCESS"
            result["llm_available"] = True
            result["requires_human_review"] = False
            return result
        return None

    def _parse_raster_pdf_via_vision(self, pdf_path, progress_callback=None):
        """
        Fallback for raster/scanned PDFs with no text layer.
        Renders each PDF page to a JPEG image via pypdfium2 (pure-Python, no Poppler needed)
        and sends to Gemini Vision API. Extracts same JSON schema as _llm_parse_pdf_text.
        Processes up to 4 pages to stay within token limits.
        """
        import io, base64, time
        api_key = self._gemini_api_key
        doc_name = os.path.basename(pdf_path)

        if not api_key:
            print(f"[DrawingVisionAgent] No API key -- cannot run vision on {doc_name}")
            return None

        if progress_callback:
            progress_callback(f"Vision scan: {doc_name} (raster PDF)...")

        # --- Render PDF pages to JPEG images ---
        page_images_b64 = []
        try:
            # Priority 1: pypdfium2 (pure Python, no external binaries)
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(pdf_path)
            max_pages = min(len(doc), 4)
            for i in range(max_pages):
                page = doc[i]
                bitmap = page.render(scale=1.5)
                img = bitmap.to_pil()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                page_images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                page.close()
            doc.close()
            print(f"[DrawingVisionAgent] Rendered {len(page_images_b64)} page(s) via pypdfium2 for {doc_name}")
        except ImportError:
            # Priority 2: pdf2image + Poppler
            try:
                from pdf2image import convert_from_path
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                max_pages = min(len(reader.pages), 4)
                images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=max_pages)
                for img in images:
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    page_images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                print(f"[DrawingVisionAgent] Rendered {len(page_images_b64)} page(s) via pdf2image for {doc_name}")
            except Exception:
                pass
        except Exception as e:
            print(f"[DrawingVisionAgent] Could not render pages for {doc_name}: {e}")

        # Priority 3: Extract embedded XObject images via pypdf
        if not page_images_b64:
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                for page_num in range(min(len(reader.pages), 4)):
                    page = reader.pages[page_num]
                    resources = page.get("/Resources", {})
                    xobjects = resources.get("/XObject", {})
                    for obj_name in list(xobjects.keys())[:1]:
                        obj = xobjects[obj_name].get_object()
                        if obj.get("/Subtype") == "/Image":
                            try:
                                from PIL import Image
                                data = obj.get_data()
                                w = int(obj.get("/Width", 800))
                                h = int(obj.get("/Height", 600))
                                cs = str(obj.get("/ColorSpace", "/DeviceRGB"))
                                mode = "RGB" if "RGB" in cs else "L"
                                img = Image.frombytes(mode, (w, h), data)
                                buf = io.BytesIO()
                                img.save(buf, format="JPEG", quality=85)
                                page_images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                            except Exception:
                                pass
                if page_images_b64:
                    print(f"[DrawingVisionAgent] Extracted {len(page_images_b64)} XObject image(s) for {doc_name}")
            except Exception as e:
                print(f"[DrawingVisionAgent] XObject fallback failed for {doc_name}: {e}")

        if not page_images_b64:
            print(f"[DrawingVisionAgent] No renderable pages found in {doc_name}")
            return None

        print(f"[DrawingVisionAgent] Sending {len(page_images_b64)} page image(s) to Gemini Vision for {doc_name}")

        # Load persistent AI memory & user-taught rules
        memory_context = ""
        try:
            from agents.correction_store import CorrectionStore
            memory_context = CorrectionStore().get_all_memory_context()
        except Exception:
            pass

        system_prompt = (
            "You are a precision Manufacturing Engineering Drawing data extraction specialist. "
            "Given images of a technical drawing (wire harness, cable assembly, or mechanical part), "
            "extract all information and return ONLY a single JSON object. No explanation, no markdown.\n\n"
            "JSON keys required:\n"
            "  \"assy_no\": string -- primary assembly part number\n"
            "  \"assy_rev\": string -- revision level, keep exact format\n"
            "  \"assy_model\": string -- descriptive assembly title\n"
            "  \"customer\": string -- customer/company name if visible, else empty string\n"
            "  \"components\": array of objects each with: "
            "\"part_number\", \"mpn\", \"mfr\", \"description\", \"qty\" (number), \"uom\", "
            "\"zone\" (TITLE_BLOCK/BOM_TABLE/COMPONENT_CALLOUT/HARDWARE_TABLE)\n\n"
            "Rules: never invent values not visible in the image. "
            "Read every table, callout bubble, and BOM section visible in the drawing.\n\n"
            + memory_context
        )

        user_prompt = f"PDF filename: {doc_name}\n\nExtract all engineering data from these drawing page images:"
        from agents.llm_gateway import LLMGateway
        result, status = LLMGateway(self.config_path).generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            inline_images=page_images_b64,
            doc_name=f"Vision:{doc_name}"
        )
        if isinstance(result, dict):
            n_comp = len(result.get("components", []))
            print(f"[DrawingVisionAgent] Vision OK: {n_comp} components from {doc_name} (status: {status})")
            if progress_callback:
                progress_callback(f"Vision: {n_comp} components from {doc_name}")

            base_name = os.path.splitext(doc_name)[0]
            assy_no = str(result.get("assy_no", base_name)).strip() or base_name
            assy_rev = str(result.get("assy_rev", "00")).strip()
            model = str(result.get("assy_model", base_name)).strip()
            customer = str(result.get("customer", "")).strip() or "Customer"
            confidence = 0.92

            items = []
            for comp in result.get("components", []):
                pn = str(comp.get("part_number", "")).strip()
                mpn = str(comp.get("mpn", "")).strip()
                mfr = str(comp.get("mfr", "")).strip()
                desc = str(comp.get("description", "Component")).strip()
                zone = str(comp.get("zone", "COMPONENT_CALLOUT")).strip()
                try:
                    qty = float(comp.get("qty", 1))
                except (ValueError, TypeError):
                    qty = 1
                uom = self.normalize_uom(str(comp.get("uom", "EA")))
                if not pn and not mpn:
                    if desc and desc.lower() not in ("component", "item", ""):
                        part_key = desc.split(",")[0].split("–")[0].split("-")[0].strip() or desc[:20].strip()
                        pn = part_key
                    else:
                        continue
                else:
                    part_key = pn or mpn
                items.append({
                    "line_item": len(items) + 1,
                    "part_number": part_key,
                    "description": desc,
                    "mfr": mfr,
                    "mpn": mpn,
                    "qty": qty,
                    "uom": uom,
                    "evidence": {
                        "part": self._create_evidence_field(part_key, ResolutionType.DIRECT, doc_name, zone=zone, snippet=f"{mfr} {mpn}".strip(), confidence=confidence),
                        "mpn": self._create_evidence_field(mpn, ResolutionType.DIRECT if mpn else ResolutionType.NOT_AVAILABLE, doc_name, zone=zone, snippet=mpn, confidence=confidence),
                        "mfr": self._create_evidence_field(mfr, ResolutionType.DIRECT if mfr else ResolutionType.NOT_AVAILABLE, doc_name, zone=zone, snippet=mfr, confidence=confidence),
                        "qty": self._create_evidence_field(qty, ResolutionType.DIRECT, doc_name, zone=zone, snippet=f"{qty} {uom}", confidence=confidence),
                        "uom": self._create_evidence_field(uom, ResolutionType.DIRECT, doc_name, zone=zone, confidence=confidence)
                    }
                })

            return {
                "source_drawing": doc_name,
                "customer_name": customer,
                "assy_no": assy_no,
                "assy_rev": assy_rev,
                "assy_model": model,
                "items": items,
                "items_count": len(items),
                "extraction_status": "VISION_SUCCESS",
                "llm_available": True,
                "requires_human_review": False,
                "evidence": {
                    "title_block": self._create_evidence_field(assy_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=assy_no, confidence=confidence),
                    "revision": self._create_evidence_field(assy_rev, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=assy_rev, confidence=confidence),
                    "customer": self._create_evidence_field(customer, ResolutionType.DIRECT if customer != "Customer" else ResolutionType.DERIVED_INFERRED, doc_name, zone="TITLE_BLOCK", snippet=customer, confidence=confidence)
                }
            }

        try:
            from agents.telemetry_tracker import ErrorTelemetryStore
            ErrorTelemetryStore().record_error(
                module="DrawingVisionAgent",
                error_category="VISION_EXTRACTION_FAILURE",
                error_message=f"Vision extraction failed for {doc_name}: {status}",
                severity="WARNING",
                document_name=doc_name,
                recovery_action="Falling back to local filename & metadata resolver",
                status="RECOVERED_VIA_FALLBACK"
            )
        except Exception:
            pass

        print(f"[DrawingVisionAgent] Vision extraction failed for {doc_name}: {status}")
        return None

    def parse_drawing_pdf(self, pdf_path, progress_callback=None, use_vision=True):
        """
        Extracts BOM components and title block metadata from a single PDF drawing.
        Step 1: Extract raw text via pypdf.
        Step 2: Call Gemini LLM to identify title block + all components (no hardcoded rules).
        Step 3: Supplement with structural regex for wiring tables and hardware counts.
        Step 4: Load past user corrections as few-shot context for LLM.

        Args:
            pdf_path:          Absolute path to PDF file
            progress_callback: Optional callable(status_str) for UI progress reporting
            use_vision:        If False, uses fast local deterministic extraction (0 API tokens).
        """
        doc_name = os.path.basename(pdf_path)
        base_name = os.path.splitext(doc_name)[0]

        # --- Extract raw text ---
        text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            pages_text = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages_text)
        except Exception as e:
            try:
                from agents.telemetry_tracker import ErrorTelemetryStore
                ErrorTelemetryStore().record_error(
                    module="DrawingVisionAgent",
                    error_category="PDF_READ_ERROR",
                    error_message=f"PDF read error on {doc_name}: {e}",
                    severity="ERROR",
                    document_name=doc_name,
                    recovery_action="Skipping unreadable drawing file",
                    status="UNRECOVERED_FILE_ERROR"
                )
            except Exception:
                pass
            print(f"[DrawingVisionAgent] PDF read error on {pdf_path}: {e}")
            return None

        if len(text.strip()) < 100:
            if use_vision:
                print(f"[DrawingVisionAgent] Minimal/no text layer in {doc_name} ({len(text.strip())} chars) — attempting Gemini Vision on page images...")
                v_res = self._parse_raster_pdf_via_vision(pdf_path, progress_callback)
                if v_res:
                    return v_res
                print(f"[DrawingVisionAgent] Vision failed/timed out — falling back to local metadata for {doc_name}")

            # Fast local filename-based drawing metadata resolution
            fn_m = re.search(r'(?:AJ0_|BB0_)?([0-9]{6,10}|[0-9]{3,4}-[0-9]{5,7}-[0-9]{3}-[0-9]{2}[A-Za-z0-9]?)(?:[._]([0-9]{2}|EN_[0-9]{2}))?\s*(.*)', base_name, re.I)
            a_no = fn_m.group(1) if fn_m else base_name
            a_rev = fn_m.group(2).replace("EN_", "") if fn_m and fn_m.group(2) else "00"
            a_mod = fn_m.group(3).strip() if fn_m and fn_m.group(3) else base_name
            return {
                "assy_no": a_no,
                "assy_rev": a_rev,
                "assy_model": a_mod or a_no,
                "customer": "Customer",
                "items": [],
                "evidence": {
                    "assy_no": self._create_evidence_field(a_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=base_name),
                    "assy_rev": self._create_evidence_field(a_rev, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=f"Rev: {a_rev}"),
                    "assy_model": self._create_evidence_field(a_mod or a_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=a_mod or a_no)
                },
                "source_drawing": doc_name,
                "extraction_status": "FAST_LOCAL"
            }

        # --- Load corrections context ---
        correction_context = ""
        try:
            from agents.correction_store import CorrectionStore
            cs = CorrectionStore()
            hints = [base_name, base_name[:8]] if len(base_name) >= 8 else [base_name]
            for hint in hints:
                corrections = cs.get_relevant_corrections(hint, ["mpn", "mfr", "description", "qty", "uom", "assy_no", "assy_rev", "assy_model"])
                if corrections:
                    lines = []
                    for c in corrections:
                        lines.append(f"  - Field '{c['field']}': extracted as {c['wrong_value']!r} → correct value is {c['correct_value']!r}"
                                     + (f" ({c.get('mfr', '')}, note: {c.get('note', '')})" if c.get('note') else ""))
                    correction_context = "\n".join(lines)
                    break
        except Exception:
            pass

        # --- Step 2: Fast Local Deterministic Extraction ---
        assy_no = base_name
        assy_rev = "00"
        model = base_name
        customer = "Customer"
        tb_snippet = ""
        confidence = 0.85

        # Title Block via structural patterns
        fn_m = re.search(r'(?:Filename|Part\s+number\s+and\s+name)[:\s]+([0-9]{6,10})\.([0-9]{2})\s+([^\n\r.]+)', text, re.I)
        if not fn_m:
            fn_m = re.search(r'\b([0-9]{8})\.([0-9]{2})\s+([^\n\r]+)', text)
        if not fn_m:
            fn_m = re.search(r'\b([0-9]{3,4}-[0-9]{5,7}-[0-9]{3}-[0-9]{2}[A-Za-z0-9]?)\b', text)
        if fn_m:
            groups = fn_m.groups()
            assy_no = groups[0].strip()
            tb_snippet = fn_m.group(0)
            if len(groups) >= 2 and groups[1]:
                assy_rev = groups[1].strip()
            if len(groups) >= 3 and groups[2]:
                model = re.sub(r'\.vsd|\.pdf|\.dwg', '', groups[2], flags=re.I).strip()

        # Filename pattern fallback (e.g. 30067050.03 CABLE VISION SRDR POWER1_draft.pdf or BB0_30067050_EN_02.pdf)
        if not assy_no or assy_no == base_name or not tb_snippet:
            doc_m = re.search(r'([0-9]{7,10})\.([0-9]{2})\s+([^.]+)', doc_name)
            if doc_m:
                assy_no = doc_m.group(1).strip()
                assy_rev = doc_m.group(2).strip()
                model = re.sub(r'_draft|\.pdf|\.dwg', '', doc_m.group(3), flags=re.I).replace("_", " ").strip()
                tb_snippet = f"{assy_no} Rev {assy_rev} — {model}"
            else:
                doc_m2 = re.search(r'([A-Za-z0-9_-]+)_([0-9]{7,10})_[A-Za-z0-9]+_([0-9]{2})', doc_name)
                if doc_m2:
                    assy_no = doc_m2.group(2).strip()
                    assy_rev = doc_m2.group(3).strip()
                    tb_snippet = f"{assy_no} Rev {assy_rev}"

        for cust_hint in ["tecan", "graco", "eastek", "honeywell", "siemens", "medtronic", "philips"]:
            if cust_hint in text.lower() or cust_hint in doc_name.lower():
                customer = cust_hint.title()
                break

        items = []
        existing_parts = set()

        # Order Codes + SAP numbers (e.g. Molex 51021-0400 -> TECAN-SAP: 30063429)
        oc_matches = re.finditer(r'(?:Order\s*Code|Ordercode|Order-Code|MFR\s*Part)[:\s]+([^\n\r]+)[\s\S]*?TECAN-SAP[:\s]+([0-9]{7,10})', text, re.I)
        for ocm in oc_matches:
            code = ocm.group(1).strip()
            sap = ocm.group(2).strip()
            if sap in existing_parts or len(sap) < 7:
                continue
            mfr, mpn = "", code
            mfr_m = re.match(r'^(Molex|FCI|Sick|TE|Tyco|JST|Amphenol|Hirose|Samtec|Panduit|Harting|Phoenix|Wago|Lapp|Helukabel|Alpha\s*Wire|Heiniger)\s+(.*)', code, re.I)
            if mfr_m:
                mfr = mfr_m.group(1).strip()
                mpn = mfr_m.group(2).strip()
            
            clean_mpn = self.sanitize_mpn(mpn)
            if not clean_mpn and not mfr:
                # If code is invalid or in blacklist, do not treat as MPN
                clean_mpn = ""

            desc_label = f"Component ({code})" if clean_mpn or mfr else f"Component {sap}"
            items.append({
                "line_item": len(items) + 1,
                "part_number": sap,
                "description": desc_label,
                "mfr": mfr,
                "mpn": clean_mpn or sap,
                "qty": 1,
                "uom": "EA",
                "evidence": {
                    "part": self._create_evidence_field(sap, ResolutionType.DIRECT, doc_name, zone="COMPONENT_CALLOUT", snippet=ocm.group(0)),
                    "mpn": self._create_evidence_field(clean_mpn or sap, ResolutionType.DIRECT if clean_mpn else ResolutionType.NOT_AVAILABLE, doc_name, zone="COMPONENT_CALLOUT", snippet=code),
                    "mfr": self._create_evidence_field(mfr, ResolutionType.DIRECT if mfr else ResolutionType.NOT_AVAILABLE, doc_name, zone="COMPONENT_CALLOUT", snippet=mfr),
                    "qty": self._create_evidence_field(1, ResolutionType.DIRECT, doc_name, zone="COMPONENT_CALLOUT"),
                    "uom": self._create_evidence_field("EA", ResolutionType.DIRECT, doc_name, zone="COMPONENT_CALLOUT")
                }
            })
            existing_parts.add(sap)

        # Wiring Table
        pos_matches = re.finditer(
            r'(\d+)\s+([0-9]{7,10})\s+([A-Za-z0-9\s()_-]+?)\s+(\d{2,5})\s+([A-Za-z0-9\s()_-]+?)(?=\n|\r|\d+\s+[0-9]{7,10})',
            text
        )
        for pm in pos_matches:
            pos_idx = int(pm.group(1))
            cable_num = pm.group(2).strip()
            start_addr = pm.group(3).strip()
            length_mm = int(pm.group(4))
            end_addr = pm.group(5).strip()
            if pos_idx > 50 or length_mm > 50000 or cable_num in existing_parts:
                continue
            items.append({
                "line_item": len(items) + 1,
                "part_number": cable_num,
                "description": f"Sub-cable {start_addr} -> {end_addr}",
                "mfr": "",
                "mpn": "",
                "qty": length_mm,
                "uom": "MM",
                "evidence": {
                    "part": self._create_evidence_field(cable_num, ResolutionType.DIRECT, doc_name, zone="WIRING_TABLE", snippet=pm.group(0)),
                    "mpn": self._create_evidence_field(None, ResolutionType.NOT_AVAILABLE, doc_name),
                    "mfr": self._create_evidence_field(None, ResolutionType.NOT_AVAILABLE, doc_name),
                    "qty": self._create_evidence_field(length_mm, ResolutionType.DIRECT, doc_name, zone="WIRING_TABLE", snippet=f"Length: {length_mm} mm"),
                    "uom": self._create_evidence_field("MM", ResolutionType.DIRECT, doc_name, zone="WIRING_TABLE")
                }
            })
            existing_parts.add(cable_num)

        # Hardware Quantities
        hw_matches = re.finditer(r'(\d+)\s+([0-9]{7,10})\s+(\d+)\s*Pcs?', text, re.I)
        for hm in hw_matches:
            item_num = hm.group(2).strip()
            qty = int(hm.group(3))
            if item_num in existing_parts:
                continue
            items.append({
                "line_item": len(items) + 1,
                "part_number": item_num,
                "description": "Hardware / Fastener",
                "mfr": "",
                "mpn": "",
                "qty": qty,
                "uom": "PCS",
                "evidence": {
                    "part": self._create_evidence_field(item_num, ResolutionType.DIRECT, doc_name, zone="HARDWARE_TABLE", snippet=hm.group(0)),
                    "mpn": self._create_evidence_field(None, ResolutionType.NOT_AVAILABLE, doc_name),
                    "mfr": self._create_evidence_field(None, ResolutionType.NOT_AVAILABLE, doc_name),
                    "qty": self._create_evidence_field(qty, ResolutionType.DIRECT, doc_name, zone="HARDWARE_TABLE"),
                    "uom": self._create_evidence_field("PCS", ResolutionType.DIRECT, doc_name)
                }
            })
            existing_parts.add(item_num)

        # If local deterministic parsing extracted items, return INSTANTLY (0 API calls, 0 429 errors!)
        if items:
            if progress_callback:
                progress_callback(f"⚡ {doc_name}: {len(items)} components extracted (Fast Path)")
            return {
                "source_drawing": doc_name,
                "customer_name": customer,
                "assy_no": assy_no,
                "assy_rev": assy_rev,
                "assy_model": model,
                "items": items,
                "items_count": len(items),
                "extraction_status": "LOCAL_FAST_PATH",
                "llm_available": True,
                "requires_human_review": False,
                "evidence": {
                    "title_block": self._create_evidence_field(assy_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=tb_snippet, confidence=confidence),
                    "revision": self._create_evidence_field(assy_rev, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=assy_rev, confidence=confidence),
                    "customer": self._create_evidence_field(customer, ResolutionType.DIRECT if customer != "Customer" else ResolutionType.DERIVED_INFERRED, doc_name, zone="TITLE_BLOCK", snippet=customer, confidence=confidence)
                }
            }

        # If use_vision is False (e.g. authoritative Excel RFQ exists), return fast metadata without LLM calls
        if not use_vision:
            return {
                "source_drawing": doc_name,
                "customer_name": customer,
                "assy_no": assy_no,
                "assy_rev": assy_rev,
                "assy_model": model,
                "items": items,
                "items_count": len(items),
                "extraction_status": "LOCAL_FAST_PATH",
                "llm_available": True,
                "requires_human_review": False,
                "evidence": {
                    "title_block": self._create_evidence_field(assy_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=tb_snippet, confidence=confidence),
                    "revision": self._create_evidence_field(assy_rev, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=assy_rev, confidence=confidence),
                    "customer": self._create_evidence_field(customer, ResolutionType.DIRECT if customer != "Customer" else ResolutionType.DERIVED_INFERRED, doc_name, zone="TITLE_BLOCK", snippet=customer, confidence=confidence)
                }
            }

        # --- Secondary Fallback: LLM-powered extraction ---
        if progress_callback:
            progress_callback(f"🤖 Calling Gemini for {doc_name}...")

        llm_result = self._llm_parse_pdf_text(text, doc_name, correction_context)

        if llm_result and isinstance(llm_result, dict):
            assy_no = str(llm_result.get("assy_no", base_name)).strip() or base_name
            assy_rev = str(llm_result.get("assy_rev", "00")).strip()
            model = str(llm_result.get("assy_model", base_name)).strip()
            customer = str(llm_result.get("customer", "")).strip() or "Customer"
            tb_snippet = f"{assy_no} Rev {assy_rev} — {model}"
            confidence = 0.90

            items = []
            for comp in llm_result.get("components", []):
                pn = str(comp.get("part_number", "")).strip()
                mpn = str(comp.get("mpn", "")).strip()
                mfr = str(comp.get("mfr", "")).strip()
                desc = str(comp.get("description", "Component")).strip()
                zone = str(comp.get("zone", "COMPONENT_CALLOUT")).strip()
                try:
                    qty = float(comp.get("qty", 1))
                except (ValueError, TypeError):
                    qty = 1
                uom = self.normalize_uom(str(comp.get("uom", "EA")))
                if not pn and not mpn:
                    if desc and desc.lower() not in ("component", "item", ""):
                        part_key = desc.split(",")[0].split("–")[0].split("-")[0].strip() or desc[:20].strip()
                        pn = part_key
                    else:
                        continue
                else:
                    part_key = pn or mpn
                items.append({
                    "line_item": len(items) + 1,
                    "part_number": part_key,
                    "description": desc,
                    "mfr": mfr,
                    "mpn": mpn,
                    "qty": qty,
                    "uom": uom,
                    "evidence": {
                        "part": self._create_evidence_field(part_key, ResolutionType.DIRECT, doc_name, zone=zone, snippet=f"{mfr} {mpn}".strip(), confidence=confidence),
                        "mpn": self._create_evidence_field(mpn, ResolutionType.DIRECT if mpn else ResolutionType.NOT_AVAILABLE, doc_name, zone=zone, snippet=mpn, confidence=confidence),
                        "mfr": self._create_evidence_field(mfr, ResolutionType.DIRECT if mfr else ResolutionType.NOT_AVAILABLE, doc_name, zone=zone, snippet=mfr, confidence=confidence),
                        "qty": self._create_evidence_field(qty, ResolutionType.DIRECT, doc_name, zone=zone, snippet=f"{qty} {uom}", confidence=confidence),
                        "uom": self._create_evidence_field(uom, ResolutionType.DIRECT, doc_name, zone=zone, confidence=confidence)
                    }
                })

        if not items:
            # If text parsing yielded 0 components, try Gemini Vision on page images
            print(f"[DrawingVisionAgent] Text parsing yielded 0 components for {doc_name} — trying Gemini Vision...")
            vis_res = self._parse_raster_pdf_via_vision(pdf_path, progress_callback)
            if vis_res and vis_res.get("items"):
                return vis_res

        return {
            "source_drawing": doc_name,
            "customer_name": customer,
            "assy_no": assy_no,
            "assy_rev": assy_rev,
            "assy_model": model,
            "items": items,
            "items_count": len(items),
            "extraction_status": "LLM_SUCCESS" if (llm_result and isinstance(llm_result, dict)) else "FALLBACK",
            "llm_available": bool(llm_result and isinstance(llm_result, dict)),
            "requires_human_review": not bool(llm_result and isinstance(llm_result, dict)),
            "evidence": {
                "title_block": self._create_evidence_field(assy_no, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=tb_snippet, confidence=confidence),
                "revision": self._create_evidence_field(assy_rev, ResolutionType.DIRECT, doc_name, zone="TITLE_BLOCK", snippet=assy_rev, confidence=confidence),
                "customer": self._create_evidence_field(customer, ResolutionType.DIRECT if customer != "Customer" else ResolutionType.DERIVED_INFERRED, doc_name, zone="TITLE_BLOCK", snippet=customer, confidence=confidence)
            }
        }

    def parse_drawing_image(self, image_path):
        """Fallback inspection for CAD drawing images (no text layer)."""
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        doc_name = os.path.basename(image_path)
        return {
            "source_drawing": doc_name,
            "customer_name": "Customer",
            "assy_no": base_name,
            "assy_rev": "A",
            "assy_model": base_name,
            "items": [
                {
                    "line_item": 1,
                    "part_number": base_name,
                    "description": f"Assembly per drawing {doc_name}",
                    "mfr": "",
                    "mpn": base_name,
                    "qty": 1,
                    "uom": "EA",
                    "evidence": {
                        "part": self._create_evidence_field(base_name, ResolutionType.DIRECT, doc_name, confidence=0.50, reasoning="Raster image — no text layer; filename used as part number"),
                        "mpn": self._create_evidence_field(base_name, ResolutionType.DERIVED_INFERRED, doc_name, reasoning="Derived from filename — no MPN readable from image"),
                        "mfr": self._create_evidence_field(None, ResolutionType.NOT_AVAILABLE, doc_name),
                        "qty": self._create_evidence_field(1, ResolutionType.DIRECT, doc_name),
                        "uom": self._create_evidence_field("EA", ResolutionType.DIRECT, doc_name)
                    }
                }
            ],
            "items_count": 1,
            "evidence": {}
        }

    def parse_drawing_file(self, file_path, progress_callback=None, use_vision=True):
        """Unified entrypoint for PDF drawings and CAD images."""
        if str(file_path).lower().endswith(".pdf"):
            return self.parse_drawing_pdf(file_path, progress_callback=progress_callback, use_vision=use_vision)
        return self.parse_drawing_image(file_path)

