# ==============================================================================
# --- ContinuumX Domain Taxonomy Engine (IPC/WHMA-A-620 & Electronics) ---
# Centralized knowledge base for Wire Harness Materials, Global Electronics
# Manufacturers, Brand Aliases, MPN Schemas, and Persistent User Extensions.
# ==============================================================================

import os
import re
import json
from typing import Dict, List, Set, Tuple, Any, Optional

# Persistent User Taxonomy Storage Location
USER_TAXONOMY_FILE = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
    'ContXs', 'learned_patterns', 'user_taxonomy_library.json'
)


# ==============================================================================
# 1. INDUSTRY-STANDARD WIRE HARNESS MATERIAL TAXONOMY (IPC/WHMA-A-620)
# Bilingual (English + German) Comprehensive Material & Hardware Taxonomy
# ==============================================================================

BUILTIN_MATERIALS: Dict[str, Dict[str, Any]] = {
    # --- A. Terminals, Pins & Contacts ---
    "flat_plug_terminal": {
        "canonical": "Flat Plug Terminal",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "flat plug terminal", "flat plug", "flat receptacle", "quick disconnect terminal",
            "spade terminal", "female quick disconnect", "male quick disconnect", "tab terminal",
            "flachstecker", "flachsteckhülse", "flachsteckhuelsen", "flachsteckzungen",
            "faston terminal", "faston receptacle", "2 x flat plug terminal", "3 x flat plug terminal",
            "4 x flat plug terminal", "flat plug 6.3mm", "flat plug 4.8mm", "flat plug 2.8mm"
        ]
    },
    "ring_terminal": {
        "canonical": "Ring Terminal",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "ring terminal", "ring tongue terminal", "eyelet terminal", "ring lug",
            "ringkabelschuh", "ringöse", "oese", "ring contact", "m3 ring terminal",
            "m4 ring terminal", "m5 ring terminal", "m6 ring terminal", "ground ring terminal"
        ]
    },
    "crimp_terminal_pin_socket": {
        "canonical": "Crimp Contact / Pin / Socket",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "crimp terminal", "terminal crimp", "crimp contact", "crimpkontakt", "crimpkontakte",
            "crimp-to-wire receptacle", "pin contact", "socket contact", "stiftkontakt", "buchsenkontakt",
            "crimp pin", "crimp socket", "receptacle terminal", "stanzkontakt", "open barrel crimp",
            "closed barrel crimp", "crimp-buchse", "crimp-stecker", "female contact", "male contact"
        ]
    },
    "ferrule_wire_end": {
        "canonical": "Wire End Ferrule",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "wire ferrule", "ferrule", "bootlace ferrule", "cord end terminal", "insulated ferrule",
            "uninsulated ferrule", "twin ferrule", "aderendhülse", "aderendhuelse", "aderendhülsen",
            "duo-aderendhülse", "ferrule 0.5mm2", "ferrule 0.75mm2", "ferrule 1.0mm2", "ferrule 1.5mm2"
        ]
    },
    "fork_spade_terminal": {
        "canonical": "Fork / Spade Terminal",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "fork terminal", "spade tongue terminal", "gabelkabelschuh", "gabelstecker",
            "flanged spade terminal", "locking fork terminal"
        ]
    },
    "bullet_splice_terminal": {
        "canonical": "Bullet / Splice Terminal",
        "category": "DESCRIPTION",
        "subfamily": "TERMINAL",
        "terms": [
            "bullet terminal", "bullet receptacle", "butt splice", "parallel splice",
            "rundstecker", "rundsteckhülse", "stoßverbinder", "quetschverbinder", "splice contact"
        ]
    },

    # --- B. Connectors, Housings & Headers ---
    "connector_housing": {
        "canonical": "Connector Housing",
        "category": "DESCRIPTION",
        "subfamily": "CONNECTOR",
        "terms": [
            "housing", "connector housing", "receptacle housing", "plug housing", "gehäuse",
            "steckergehäuse", "buchsengehäuse", "crimp housing", "wire-to-board housing",
            "wire-to-wire housing", "2pin housing", "3pin housing", "4pin housing", "6pin housing",
            "8pin housing", "10pin housing", "12pin housing", "16pin housing", "20pin housing",
            "micro-fit housing", "mini-fit housing", "micromatch housing", "d-sub housing"
        ]
    },
    "header_wafer_shroud": {
        "canonical": "PCB Header / Wafer",
        "category": "DESCRIPTION",
        "subfamily": "CONNECTOR",
        "terms": [
            "header", "pin header", "wafer", "shrouded header", "stiftleiste", "messerleiste",
            "buchsenleiste", "pcb header", "right angle header", "straight header", "box header"
        ]
    },
    "dsub_connector": {
        "canonical": "D-Sub Connector",
        "category": "DESCRIPTION",
        "subfamily": "CONNECTOR",
        "terms": [
            "d-sub", "d-sub connector", "dsub connector", "d-sub crimp-buchse", "d-sub crimp-stecker",
            "sub-d", "d-sub 9pin", "d-sub 15pin", "d-sub 25pin", "d-sub 37pin", "d-sub 50pin",
            "hd d-sub", "d-sub hood", "d-sub metal backshell", "d-sub metallhaube"
        ]
    },
    "circular_industrial_connector": {
        "canonical": "Circular / Industrial Connector",
        "category": "DESCRIPTION",
        "subfamily": "CONNECTOR",
        "terms": [
            "m8 connector", "m12 connector", "circular connector", "rundsteckverbinder",
            "deutsch connector", "amphenol industrial", "harting han", "heavy duty connector"
        ]
    },
    "connector_accessories": {
        "canonical": "Connector Accessories (TPA, CPA, Backshell, Seal)",
        "category": "DESCRIPTION",
        "subfamily": "CONNECTOR",
        "terms": [
            "backshell", "strain relief", "tpa", "terminal position assurance", "cpa",
            "connector position assurance", "wedge lock", "cavity plug", "blindstopfen",
            "wire seal", "single wire seal", "dichtung", "zugentlastung", "haube", "endbell"
        ]
    },

    # --- C. Raw Cables, Wires & Conductors ---
    "cable_assembly_raw": {
        "canonical": "Cable Assembly / Multiconductor Cable",
        "category": "DESCRIPTION",
        "subfamily": "CABLE",
        "terms": [
            "cable", "cable assembly", "multiconductor cable", "steurkabel", "steuerleitung",
            "kabel", "leitung", "rundkabel", "flachbandkabel", "ribbon cable", "coaxial cable",
            "koaxialkabel", "twisted pair", "shielded cable", "geschirmte leitung", "unshielded cable",
            "sensor cable", "power cable", "hybrid cable", "trailing cable", "drag chain cable",
            "cable rnn", "cable fuse to filter"
        ]
    },
    "hookup_wire_single_core": {
        "canonical": "Hookup Wire / Stranded Wire",
        "category": "DESCRIPTION",
        "subfamily": "CABLE",
        "terms": [
            "hookup wire", "single core wire", "single wire", "stranded wire", "litze",
            "einzelader", "schaltdraht", "pvc wire", "silicone wire", "ptfe wire", "teflon wire",
            "cross-linked wire", "xlpe wire", "ul1007", "ul1015", "ul1061", "ul1569", "ul2464"
        ]
    },

    # --- D. Protection, Tubing & Sleeving ---
    "heat_shrink_tubing": {
        "canonical": "Heat Shrink Tubing",
        "category": "DESCRIPTION",
        "subfamily": "PROTECTION",
        "terms": [
            "heat shrink", "heat shrink tube", "heat shrink tubing", "heatshrink", "schrumpfschlauch",
            "dual-wall heat shrink", "adhesive lined heat shrink", "polyolefin tube", "2:1 heat shrink",
            "3:1 heat shrink", "4:1 heat shrink", "warmeschrumpfschlauch", "kynar tube", "viton sleeve"
        ]
    },
    "protective_sleeving_conduit": {
        "canonical": "Protective Sleeving / Conduit / Loom",
        "category": "DESCRIPTION",
        "subfamily": "PROTECTION",
        "terms": [
            "braided sleeve", "expandable sleeving", "pet sleeving", "geflechtschlauch",
            "split loom", "corrugated conduit", "wellrohr", "fiberglass sleeve", "glasfaserschlauch",
            "spiral wrap", "spiralband", "protection tube", "schutzschlauch", "edge protection"
        ]
    },
    "grommet_molded_boot": {
        "canonical": "Grommet / Molded Boot",
        "category": "DESCRIPTION",
        "subfamily": "PROTECTION",
        "terms": [
            "grommet", "rubber grommet", "kabeltülle", "knickschutztülle", "molded boot",
            "formtülle", "tülle", "cable gland", "kabelverschraubung"
        ]
    },

    # --- E. Magnetics & EMI Suppression ---
    "ferrite_core": {
        "canonical": "Ferrite Core / Bead",
        "category": "DESCRIPTION",
        "subfamily": "MAGNETICS",
        "terms": [
            "ferrite", "ferrite core", "ferrite bead", "split ferrite", "snap-on ferrite",
            "ferritkern", "klappferrit", "ringkern", "toroid ferrite", "emi filter",
            "ferrite clamp", "ferrite sleeve", "rfi suppression core"
        ]
    },
    "shielding_materials": {
        "canonical": "Shielding Foil / Tape / Braid",
        "category": "DESCRIPTION",
        "subfamily": "MAGNETICS",
        "terms": [
            "copper tape", "aluminum tape", "shielding tape", "shielding braid", "schirmgeflecht",
            "copper foil", "kupferband", "emv schirmung", "grounding braid", "masseband"
        ]
    },

    # --- F. Fasteners, Labels & Hardware ---
    "cable_ties_fasteners": {
        "canonical": "Cable Tie / Fastener / Clip",
        "category": "DESCRIPTION",
        "subfamily": "HARDWARE",
        "terms": [
            "cable tie", "zip tie", "kabelbinder", "wire tie", "releasable cable tie",
            "edge clip", "fir tree clip", "adhesive mount", "klebesockel", "kabelhalter",
            "wire saddle", "standoff", "distanzbolzen"
        ]
    },
    "marking_labels": {
        "canonical": "Marker / Identification Label",
        "category": "DESCRIPTION",
        "subfamily": "HARDWARE",
        "terms": [
            "label", "marker sleeve", "heat shrink label", "wrap-around label", "kennzeichnungsschild",
            "kabelmarkierer", "flag label", "etiquette", "cable label", "wire label"
        ]
    },

    # --- G. Manufacturing Instructions & Assembly Process Callouts ---
    "assembly_process_notes": {
        "canonical": "Process & Assembly Instruction",
        "category": "DESCRIPTION",
        "subfamily": "PROCESS_NOTE",
        "terms": [
            "all 3 wires passed through", "the ferrite two times", "cut unused wires",
            "strip length", "abisolierlänge", "crimp height", "crimphöhe", "pull force",
            "auszugskraft", "fold back shield", "twist wires", "ultrasonic weld",
            "continuity test", "hipot test", "high voltage test", "rohs compliant", "ul conform"
        ]
    }
}


# ==============================================================================
# 2. GLOBAL ELECTRONICS & WIRE HARNESS MANUFACTURERS (165+ VENDORS)
# ==============================================================================

GLOBAL_MANUFACTURERS: Dict[str, Dict[str, Any]] = {
    # Major Connector Manufacturers
    "TE Connectivity": {"aliases": ["TE", "TYCO", "TYCO ELECTRONICS", "AMP", "DEUTSCH", "RAYCHEM", "SCHRACK", "INTERCONTEC", "AGASTA"]},
    "Molex": {"aliases": ["MOLEX INC", "MOLEX LLC", "MICRO-FIT", "MINI-FIT", "KK", "SPOX", "CLIK-MATE", "SL"]},
    "Amphenol": {"aliases": ["AMPHENOL FCI", "AFCI", "AMPHENOL INDUSTRIAL", "AMPHENOL SINE", "AMPHENOL TUCHEL", "AMPHENOL SOCAPEX"]},
    "JST": {"aliases": ["J.S.T.", "JST MFG", "JST SALES", "JST CORP"]},
    "Hirose": {"aliases": ["HRS", "HIROSE ELECTRIC", "HIROSE CONNECTORS"]},
    "Samtec": {"aliases": ["SAMTEC INC"]},
    "Harting": {"aliases": ["HARTING ELEKTRONIK", "HARTING TECHNOLOGY GROUP"]},
    "Phoenix Contact": {"aliases": ["PHOENIX", "PHOENIX CONTACT GMBH"]},
    "WAGO": {"aliases": ["WAGO KONTAKTTECHNIK"]},
    "Weidmüller": {"aliases": ["WEIDMULLER", "WEIDMUELLER"]},
    "Deltron": {"aliases": ["DELTRON AG", "DELTRON CONNECTORS"]},
    "FCI": {"aliases": ["FCI CONNECTORS", "BERG ELECTRONICS"]},
    "Lemo": {"aliases": ["LEMO SA", "LEMO USA"]},
    "ODU": {"aliases": ["ODU STECKVERBINDUNGSSYSTEME"]},
    "Binder": {"aliases": ["FRANZ BINDER", "BINDER CONNECTORS"]},
    "Lumberg": {"aliases": ["LUMBERG CONNECT", "LUMBERG AUTOMATION"]},
    "Yazaki": {"aliases": ["YAZAKI CORP", "YAZAKI NORTH AMERICA"]},
    "Sumitomo": {"aliases": ["SUMITOMO WIRING SYSTEMS", "SWS"]},
    "Aptiv": {"aliases": ["DELPHI", "DELPHI PACKARD", "DELPHI AUTOMOTIVE"]},
    "MH Connectors": {"aliases": ["MH", "MH CONNECTORS LTD"]},
    "NorComp": {"aliases": ["NORCOMP INC"]},
    "Cinch Connectivity": {"aliases": ["CINCH", "CINCH CONNECTORS"]},
    "Glenair": {"aliases": ["GLENAIR INC"]},
    "ITT Cannon": {"aliases": ["CANNON", "VEAM"]},
    "ERNI": {"aliases": ["ERNI ELECTRONICS", "ERNI PRODUCTION"]},
    "Wurth Elektronik": {"aliases": ["WÜRTH ELEKTRONIK", "WURTH", "WE", "WURTH ELECTRONICS"]},
    "Fischer Connectors": {"aliases": ["FISCHER"]},
    "Sourian": {"aliases": ["SOURIAU-SUNBANK", "SUNBANK"]},
    "Anderson Power": {"aliases": ["APP", "ANDERSON POWER PRODUCTS"]},
    "Kyocera AVX": {"aliases": ["AVX", "KYOCERA"]},
    "Rosenberger": {"aliases": ["ROSENBERGER HOCHFREQUENZTECHNIK"]},
    "Schurter": {"aliases": ["SCHURTER AG", "SCHURTER ELECTRONIC"]},

    # Wire & Raw Cable Manufacturers
    "Alpha Wire": {"aliases": ["ALPHA", "ALPHA WIRE CORP"]},
    "Belden": {"aliases": ["BELDEN WIRE", "BELDEN INC"]},
    "Lapp Kabel": {"aliases": ["LAPP", "LAPP GROUP", "ÖLFLEX", "OLFLEX", "UNITRONIC"]},
    "Helukabel": {"aliases": ["HELU", "HELUKABEL GMBH"]},
    "Huber+Suhner": {"aliases": ["HUBER SUHNER", "H+S", "RADOPAL", "RADOX"]},
    "Leoni": {"aliases": ["LEONI AG", "LEONI CABLE"]},
    "Prysmian": {"aliases": ["PRYSMIAN GROUP", "DRAKA", "GENERAL CABLE"]},
    "Nexans": {"aliases": ["NEXANS SA"]},
    "Southwire": {"aliases": ["SOUTHWIRE COMPANY"]},
    "IGUS": {"aliases": ["IGUS GMBH", "CHAINFLEX"]},
    "Habia Cable": {"aliases": ["HABIA"]},
    "SAB Broeckskes": {"aliases": ["SAB", "BROECKSKES"]},
    "Corning": {"aliases": ["CORNING CABLE SYSTEMS"]},
    "Gore": {"aliases": ["W. L. GORE", "GORE-TEX CABLES"]},
    "Judd Wire": {"aliases": ["JUDD"]},
    "Carlisle": {"aliases": ["CARLISLEIT", "CARLISLE INTERCONNECT"]},
    "Teledyne": {"aliases": ["TELEDYNE REYNOLDS", "TELEDYNE CABLE"]},

    # Protection, Heat Shrink, Fasteners & Tubing
    "HellermannTyton": {"aliases": ["HELLERMANN", "HELLERMANNTYTON GMBH"]},
    "Panduit": {"aliases": ["PANDUIT CORP"]},
    "3M": {"aliases": ["3M COMPANY", "3M ELECTRONICS"]},
    "Techflex": {"aliases": ["TECHFLEX INC"]},
    "Brady": {"aliases": ["BRADY CORP", "BRADY IDENTIFICATION"]},
    "Essentra": {"aliases": ["ESSENTRA COMPONENTS", "RICHCO"]},
    "Heyco": {"aliases": ["HEYCO PRODUCTS"]},
    "KST": {"aliases": ["K.S. TERMINALS", "KS TERMINALS"]},
    "JST Terminals": {"aliases": ["JST TERMINAL"]},
    "Vogt": {"aliases": ["VOGT AG", "VOGT VERBINDUNGSTECHNIK"]},

    # Magnetics, Passives & EMC
    "Fair-Rite": {"aliases": ["FAIR-RITE PRODUCTS CORP", "FAIR RITE"]},
    "TDK": {"aliases": ["TDK CORP", "EPCOS"]},
    "Murata": {"aliases": ["MURATA ELECTRONICS", "MURATA MFG"]},
    "KEMET": {"aliases": ["KEMET ELECTRONICS", "TOKIN"]},
    "Vishay": {"aliases": ["VISHAY INTERTECHNOLOGY", "DALE", "DRALORIC"]},
    "Bourns": {"aliases": ["BOURNS INC"]},
    "Ferroxcube": {"aliases": ["FERROXCUBE", "PHILIPS COMPONENTS"]},
    "Laird": {"aliases": ["LAIRD PERFORMANCE MATERIALS", "LAIRD TECHNOLOGIES"]},
    "Schaffner": {"aliases": ["SCHAFFNER EMV", "SCHAFFNER GROUP"]},

    # Sensors, Automation & Swiss/European OEMs
    "Sick": {"aliases": ["SICK AG", "SICK SENSOR"]},
    "Omron": {"aliases": ["OMRON ELECTRONICS", "OMRON CORP"]},
    "IFM": {"aliases": ["IFM ELECTRONIC"]},
    "Turck": {"aliases": ["HANS TURCK", "TURCK BANNER"]},
    "Pepperl+Fuchs": {"aliases": ["P+F", "PEPPERL FUCHS"]},
    "Balluff": {"aliases": ["BALLUFF GMBH"]},
    "Baumer": {"aliases": ["BAUMER GROUP", "BAUMER ELECTRIC"]},
    "Tecan": {"aliases": ["TECAN SCHWEIZ AG", "TECAN GROUP", "TECAN SP", "TECAN SAP"]},
    "Distrelec": {"aliases": ["DISTRELEC GROUP", "SCHURICHT"]},
    "Heiniger": {"aliases": ["HEINIGER CABLE", "HEINIGER AG"]}
}


# ==============================================================================
# 3. HIGH-PRECISION MPN SCHEMAS & BRAND PARSING RULES
# ==============================================================================

MPN_BRAND_PATTERNS = [
    # Molex 10-digit zero-prefixed & 5-4 dashed (e.g. 0430300004, 43030-0004, 43025-0600, 50079-8000, 51021-0600)
    (r'\b0(\d{5})(\d{4})\b', "Molex"),
    (r'\b(\d{5})-(\d{4})\b', "Molex"),
    (r'\b(\d{3})-(\d{2})-(\d{4})\b', "Molex"),
    (r'\b(43025|43030|43045|43645|43640|50079|51021|50372|50212|105300|105313|172256|172258)-?\d{4}\b', "Molex"),

    # TE Connectivity / AMP (e.g. 338095-x, 338096-x, 1-967402-1, 282104-1, 770342-1)
    (r'\b(338095|338096|338097|215079|215083|282104|770342|964286|967402)-[0-9]\b', "TE Connectivity"),
    (r'\b[0-9]-(\d{6,7})-[0-9]\b', "TE Connectivity"),
    (r'\b(DT06|DT04|DTM06|DTM04|DTP06|HDP24|DRC16)-[0-9A-Z\-]+\b', "TE Connectivity (Deutsch)"),

    # JST Connector Series (e.g. XHP-x, SXH-001T-P0.6, PHR-x, SPH-002T-P0.5S, VHR-x, PAP-x)
    (r'\b(XHP|PHR|VHR|PAP|EHR|SHR|GHR|SUR|SAN|SZN|PUD|B2B|B3B|B4B|B6B)-[0-9A-Z\-]+\b', "JST"),
    (r'\b(SXH|SPH|SVH|SPHD|SSH|SGF|SPAL|SEH)-[0-9A-Z\.\-]+\b', "JST"),

    # Deltron D-Sub & Swiss Precision (e.g. DT 15 SX, DT 09 PX, SX1, D-Sub Hardware)
    (r'\bDT\s*\d{2}\s*[SP][XF]\b|\bDT\d{2}[SP][XF]\b', "Deltron"),
    (r'\bSX1\b|\bPX1\b|\bFL15\b|\bFL09\b', "Deltron"),

    # Raychem / HellermannTyton Heat Shrink & Markers
    (r'\b(RNF-100|VERSAFIT|DR-25|ATUM|CGPT|ZH-100|TMS-SCE)-[0-9A-Z\/\.\-]+\b', "Raychem"),
    (r'\b(PLT1M|PLT2S|PLT3S|PLT4S)-[0-9A-Z\-]+\b', "Panduit"),
    (r'\b(T18R|T50R|T120R|OS181|MB3A|CT18)-[0-9A-Z\-]+\b', "HellermannTyton"),

    # Fair-Rite / Würth Ferrite Cores
    (r'\b(2643|2644|2843|0443|0444)\d{6}\b', "Fair-Rite"),
    (r'\b(7427\d{4}|7427\d{5})\b', "Wurth Elektronik")
]


# ==============================================================================
# 4. TAXONOMY STORAGE & ACTIVE LEARNING PERSISTENCE ENGINE
# ==============================================================================

class DomainTaxonomyEngine:
    """
    Central repository knowledge engine for Wire Harness Materials, Manufacturers,
    and MPN Schemas with dynamic persistent user expansion.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DomainTaxonomyEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self._initialized = True
        self.materials: Dict[str, Dict[str, Any]] = dict(BUILTIN_MATERIALS)
        self.manufacturers: Dict[str, Dict[str, Any]] = dict(GLOBAL_MANUFACTURERS)
        self.mpn_patterns = list(MPN_BRAND_PATTERNS)
        self.user_custom_entries: Dict[str, List[Dict[str, Any]]] = {
            "MATERIALS": [],
            "MANUFACTURERS": [],
            "MPNS": []
        }
        self.load_user_library()

    def load_user_library(self):
        """Loads user-taught persistent custom vocabulary from local app data."""
        try:
            if os.path.exists(USER_TAXONOMY_FILE):
                with open(USER_TAXONOMY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.user_custom_entries = data

                        # Merge user materials
                        for u_mat in data.get("MATERIALS", []):
                            key = u_mat.get("key", "").strip() or re.sub(r'\W+', '_', u_mat.get("canonical", "").lower())
                            if key:
                                self.materials[key] = {
                                    "canonical": u_mat.get("canonical", key),
                                    "category": u_mat.get("category", "DESCRIPTION"),
                                    "subfamily": u_mat.get("subfamily", "CUSTOM"),
                                    "terms": u_mat.get("terms", []),
                                    "source": "User Library"
                                }

                        # Merge user manufacturers
                        for u_mfr in data.get("MANUFACTURERS", []):
                            name = u_mfr.get("name", "").strip()
                            if name:
                                self.manufacturers[name] = {
                                    "aliases": u_mfr.get("aliases", []),
                                    "source": "User Library"
                                }
        except Exception as ex:
            print(f"[DomainTaxonomyEngine] Failed to load user taxonomy: {ex}")

    def save_user_library(self):
        """Persists user custom additions to JSON."""
        try:
            os.makedirs(os.path.dirname(USER_TAXONOMY_FILE), exist_ok=True)
            with open(USER_TAXONOMY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_custom_entries, f, indent=2)
        except Exception as ex:
            print(f"[DomainTaxonomyEngine] Failed to save user taxonomy: {ex}")

    def add_custom_material(self, canonical_name: str, terms: List[str], subfamily: str = "CUSTOM") -> bool:
        """Adds and persists a new wire harness material phrase to the library."""
        if not canonical_name or not terms: return False
        clean_terms = [t.strip().lower() for t in terms if t and len(t.strip()) >= 2]
        if not clean_terms: return False

        entry = {
            "key": re.sub(r'\W+', '_', canonical_name.lower()),
            "canonical": canonical_name.strip(),
            "category": "DESCRIPTION",
            "subfamily": subfamily.upper(),
            "terms": clean_terms
        }
        self.materials[entry["key"]] = {
            "canonical": entry["canonical"],
            "category": "DESCRIPTION",
            "subfamily": entry["subfamily"],
            "terms": clean_terms,
            "source": "User Library"
        }

        # Remove existing if overwriting
        self.user_custom_entries["MATERIALS"] = [m for m in self.user_custom_entries.get("MATERIALS", []) if m.get("canonical") != canonical_name]
        self.user_custom_entries["MATERIALS"].append(entry)
        self.save_user_library()
        return True

    def add_custom_manufacturer(self, name: str, aliases: List[str]) -> bool:
        """Adds and persists a new component manufacturer with aliases."""
        if not name: return False
        clean_name = name.strip()
        clean_aliases = [a.strip().upper() for a in aliases if a and len(a.strip()) >= 2]
        
        self.manufacturers[clean_name] = {
            "aliases": clean_aliases,
            "source": "User Library"
        }

        self.user_custom_entries["MANUFACTURERS"] = [m for m in self.user_custom_entries.get("MANUFACTURERS", []) if m.get("name") != clean_name]
        self.user_custom_entries["MANUFACTURERS"].append({
            "name": clean_name,
            "aliases": clean_aliases
        })
        self.save_user_library()
        return True

    def delete_custom_entry(self, entry_type: str, identifier: str) -> bool:
        """Deletes a user custom entry by identifier."""
        entry_type = entry_type.upper()
        if entry_type == "MATERIALS":
            self.user_custom_entries["MATERIALS"] = [m for m in self.user_custom_entries.get("MATERIALS", []) if m.get("canonical") != identifier and m.get("key") != identifier]
            self.materials.pop(identifier, None)
            self.save_user_library()
            return True
        elif entry_type == "MANUFACTURERS":
            self.user_custom_entries["MANUFACTURERS"] = [m for m in self.user_custom_entries.get("MANUFACTURERS", []) if m.get("name") != identifier]
            self.manufacturers.pop(identifier, None)
            self.save_user_library()
            return True
        return False

    def get_all_material_phrases(self) -> List[Tuple[str, str, str]]:
        """Returns sorted list of (phrase, canonical_name, subfamily) ordered longest first."""
        phrases = []
        for mat in self.materials.values():
            canon = mat["canonical"]
            subfam = mat.get("subfamily", "MATERIAL")
            for t in mat.get("terms", []):
                phrases.append((t, canon, subfam))
        # Longest match first to avoid sub-phrase collisions
        phrases.sort(key=lambda x: len(x[0]), reverse=True)
        return phrases

    def get_all_manufacturer_tokens(self) -> List[Tuple[str, str]]:
        """Returns list of (token_regex, canonical_brand_name)."""
        tokens = []
        for brand, info in self.manufacturers.items():
            tokens.append((brand, brand))
            for a in info.get("aliases", []):
                tokens.append((a, brand))
        tokens.sort(key=lambda x: len(x[0]), reverse=True)
        return tokens


# Export Singleton Engine
TaxonomyEngine = DomainTaxonomyEngine()
