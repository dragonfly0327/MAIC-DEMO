# ==============================================================================
# --- ContinuumX Intelligent Parameter Parser ---
# Robust, natural-language parameter extractor for chat messages and prompts.
# Extracts Customer Name, Project Title, Commodity, RFQ Number, Target Price,
# EAU, Default MOQs, and Custom MOQs without fragile keyword truncation.
# ==============================================================================

import re
from typing import Dict, Any, List, Optional, Tuple


def _clean_value(raw_val: str) -> str:
    """Strips leading/trailing filler verbs, conjunctions, quotes, and punctuation."""
    if not raw_val:
        return ""
    val = raw_val.strip()
    
    # Strip quotes if present
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
        
    # Strip common leading filler phrases
    filler_leading = [
        r'^(?:change|changed|changes)\s+(?:to|into|as)\s+',
        r'^(?:set|sets|setting)\s+(?:to|into|as)\s+',
        r'^(?:update|updated|updates)\s+(?:to|into|as)\s+',
        r'^(?:make|makes)\s+(?:it|to|into|as)\s+',
        r'^(?:to|into|as|is|was|are|should\s+be|must\s+be|=|:)\s+',
    ]
    for fp in filler_leading:
        val = re.sub(fp, '', val, flags=re.IGNORECASE).strip()

    # Split off trailing conjunctions / next parameter keywords
    trailing_split_patterns = [
        r'\s+(?:and\s+)?(?:set\s+)?(?:default\s+)?(?:moqs?|assigned\s+moqs?)\b.*$',
        r'\s+(?:and\s+)?(?:set\s+)?(?:target\s+price|tp)\b.*$',
        r'\s+(?:and\s+)?(?:set\s+)?(?:eau|annual\s+usage)\b.*$',
        r'\s+(?:and\s+)?(?:set\s+)?(?:commodity|type)\b.*$',
        r'\s+(?:and\s+)?(?:set\s+)?(?:proj(?:ec)?t|title)\b.*$',
        r'\s+(?:and\s+)?(?:set\s+)?(?:rfq\s*(?:number|id|no)?)\b.*$',
    ]
    for tsp in trailing_split_patterns:
        val = re.sub(tsp, '', val, flags=re.IGNORECASE).strip()

    # Strip surrounding quotes again if inner was quoted
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()

    return val


def parse_bom_parameters(text: str) -> Dict[str, Any]:
    """
    Extracts all parameter overrides from natural language chat input.
    """
    if not text:
        return {"has_updates": False}

    res = {
        "customer_name": None,
        "project_title": None,
        "commodity": None,
        "rfq_number": None,
        "target_price": None,
        "eau": None,
        "default_moqs": [],
        "custom_moqs": {},
        "has_updates": False
    }

    # --------------------------------------------------------------------------
    # 1. CUSTOMER NAME
    # --------------------------------------------------------------------------
    cust_c = re.search(
        r'(?:cust(?:omwer|omer)?|client|company)(?:\s+name)?\s*.*?"([^"]+)"',
        text, re.IGNORECASE
    )
    cust_a = re.search(
        r'(?:change|set|update|make)\s+(?:the\s+)?(?:cust(?:omwer|omer)?|client|company)(?:\s+name)?\s+(?:to|into|as|=|:)\s*([^"\n\r,]+)',
        text, re.IGNORECASE
    )
    cust_b = re.search(
        r'(?:cust(?:omwer|omer)?|client|company)(?:\s+name)?\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)\s*([^"\n\r,]+)',
        text, re.IGNORECASE
    )

    cust_raw = None
    if cust_c:
        cust_raw = cust_c.group(1)
    elif cust_a:
        cust_raw = cust_a.group(1)
    elif cust_b:
        cust_raw = cust_b.group(1)

    if cust_raw:
        cust_clean = _clean_value(cust_raw)
        if cust_clean and not any(k in cust_clean.lower() for k in ['summary', 'chart', 'list', 'top', 'stage']):
            res["customer_name"] = cust_clean
            res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 2. PROJECT TITLE
    # --------------------------------------------------------------------------
    proj_c = re.search(
        r'(?:proj(?:ec)?t\s*(?:title|name)?|title)\s*.*?"([^"]+)"',
        text, re.IGNORECASE
    )
    proj_a = re.search(
        r'(?:change|set|update)\s+(?:the\s+)?(?:proj(?:ec)?t\s*(?:title|name)?|title)\s+(?:to|into|as|=|:)\s*([^"\n\r,]+)',
        text, re.IGNORECASE
    )
    proj_b = re.search(
        r'(?:proj(?:ec)?t\s*(?:title|name)?|title)\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)\s*([^"\n\r,]+)',
        text, re.IGNORECASE
    )

    proj_raw = None
    if proj_c:
        proj_raw = proj_c.group(1)
    elif proj_a:
        proj_raw = proj_a.group(1)
    elif proj_b:
        proj_raw = proj_b.group(1)

    if proj_raw:
        proj_clean = _clean_value(proj_raw)
        if proj_clean and not any(k in proj_clean.lower() for k in ['summary', 'chart', 'process', 'proceed', 'launch']):
            res["project_title"] = proj_clean
            res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 3. COMMODITY
    # --------------------------------------------------------------------------
    comm_m = re.search(
        r'(?:commodity|type)\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)?\s*["\']?([^"\'\n\r,]+)["\']?',
        text, re.IGNORECASE
    )
    if comm_m:
        raw_c = _clean_value(comm_m.group(1))
        vlow = raw_c.lower()
        if not any(k in vlow for k in ['summary', 'chart', 'process', 'proceed', 'launch']):
            if "pcb" in vlow or "board" in vlow: raw_c = "PCBA"
            elif "wire" in vlow or "harness" in vlow or "cable" in vlow: raw_c = "Wire Harness"
            elif "fiber" in vlow or "fibre" in vlow or "optic" in vlow: raw_c = "FIBER Optic"
            elif "box" in vlow or "build" in vlow: raw_c = "BoxBuild"
            elif "mod" in vlow: raw_c = "Module"
            res["commodity"] = raw_c
            res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 4. RFQ NUMBER
    # --------------------------------------------------------------------------
    rfq_m = re.search(
        r'(?:rfq\s*(?:number|id|no)?)\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)?\s*["\']?([a-z0-9_-]+)["\']?',
        text, re.IGNORECASE
    )
    if rfq_m:
        val = rfq_m.group(1).strip()
        if val.lower() not in ["number", "id", "no", "is", "was", "to"]:
            res["rfq_number"] = val
            res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 5. TARGET PRICE
    # --------------------------------------------------------------------------
    tp_m = re.search(
        r'(?:target\s*price|tp)\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)?\s*\$?([0-9\.]+)',
        text, re.IGNORECASE
    )
    if tp_m:
        res["target_price"] = f"${tp_m.group(1).strip()}"
        res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 6. EAU
    # --------------------------------------------------------------------------
    eau_m = re.search(
        r'(?:eau|annual\s*usage)\s*(?:change\s+to|set\s+to|update\s+to|is|=|was|:|to|as)?\s*([0-9,]+)',
        text, re.IGNORECASE
    )
    if eau_m:
        res["eau"] = eau_m.group(1).replace(",", "").strip()
        res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 7. DEFAULT MOQS
    # --------------------------------------------------------------------------
    def_m = re.search(
        r'(?:set\s+)?(?:default\s+)?(?:moq|moqs|assigned\s+moqs)\s*(?:change\s+to|set\s+to|update\s+to|to|into|is|=|was|:)\s*([0-9,\s\[\]]+)',
        text, re.IGNORECASE
    )
    if not def_m:
        def_m = re.search(r'(?:default\s+moqs?|moqs?)\s*[:=]?\s*([0-9,\s\[\]]+)', text, re.IGNORECASE)

    if def_m:
        raw_def = def_m.group(1).splitlines()[0]
        if "except" in raw_def.lower():
            raw_def = raw_def.lower().split("except")[0]
        moqs = [int(n) for n in re.findall(r'\b\d+\b', raw_def) if int(n) > 0]
        if moqs:
            res["default_moqs"] = moqs
            res["has_updates"] = True

    # --------------------------------------------------------------------------
    # 8. CUSTOM MOQS PER ASSEMBLY
    # --------------------------------------------------------------------------
    custom_moqs = {}
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean or "default" in line_clean.lower():
            continue
        assy_match = re.search(r'\b([a-z0-9_]{2,}(?:-[a-z0-9_]+)+)\b', line_clean, re.IGNORECASE)
        if assy_match:
            assy_id = assy_match.group(1).strip()
            line_sans_assy = line_clean.replace(assy_id, '')
            nums = [int(n) for n in re.findall(r'\b\d+\b', line_sans_assy) if int(n) > 0]
            if nums:
                custom_moqs[assy_id] = nums

    inline_matches = re.finditer(
        r'(?:assembly|assy|part|for)?\s*([a-z0-9_]{2,}(?:-[a-z0-9_]+)+)\s*(?:use|has|set|with|is|=|:|\->)?\s*(?:custom\s*)?(?:moq|mo)?\s*(?:change\s+to|set\s+to|to|is|=|was|:|\->)?\s*([0-9,\s]+)',
        text, re.IGNORECASE
    )
    for cm in inline_matches:
        assy_id = cm.group(1).strip()
        nums = [int(n) for n in re.findall(r'\b\d+\b', cm.group(2)) if int(n) > 0]
        if assy_id and nums and assy_id.lower() not in ["default", "custom", "the", "a"]:
            custom_moqs[assy_id] = nums

    if custom_moqs:
        res["custom_moqs"] = custom_moqs
        res["has_updates"] = True

    return res
