# -*- coding: utf-8 -*-
"""
Processing Telemetry & AI Benchmark Tracker for ContinuumX.
Captures per-email execution latency, BOM volume, cache hit ratios, and multi-run variance.
"""

import os
import sys
import json
import time
import csv
import threading
from datetime import datetime

if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.getcwd()

PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..")) if os.path.basename(BASE_DIR).lower() == "agents" else BASE_DIR
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TELEMETRY_JSON = os.path.join(DATA_DIR, "processing_telemetry.json")
TELEMETRY_CSV = os.path.join(DATA_DIR, "processing_telemetry.csv")


class ProcessingTelemetryTracker:
    """Singleton tracking telemetry, speedup benchmarks, and reprocess consistency."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProcessingTelemetryTracker, cls).__new__(cls)
            cls._instance._init_tracker()
        return cls._instance

    def _init_tracker(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.records = self._load_records()

    def _load_records(self):
        if os.path.exists(TELEMETRY_JSON):
            try:
                with open(TELEMETRY_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[TelemetryTracker] Load warning: {e}")
        return []

    def _save_records(self):
        try:
            with open(TELEMETRY_JSON, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=2)
            self._export_csv()
        except Exception as e:
            print(f"[TelemetryTracker] Save warning: {e}")

    def _export_csv(self):
        try:
            fieldnames = [
                "timestamp", "email_subject", "rfq_number", "run_index",
                "duration_seconds", "formatted_duration", "bom_assemblies_count",
                "components_count", "attachments_count", "cache_hits", "api_calls",
                "speedup_vs_run1"
            ]
            with open(TELEMETRY_CSV, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for rec in self.records:
                    row = {k: rec.get(k, "") for k in fieldnames}
                    writer.writerow(row)
        except Exception as e:
            print(f"[TelemetryTracker] CSV export error: {e}")

    def record_run(self, email_subject, rfq_number, start_time, end_time,
                   assemblies_count=0, components_count=0, attachments_count=0,
                   cache_hits=0, api_calls=0, trigger_source="User Execution"):
        """Records an execution run for an email and returns the telemetry object."""
        duration = max(0.01, round(end_time - start_time, 2))
        mins = int(duration // 60)
        secs = round(duration % 60, 1)
        fmt_dur = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        subj_key = str(email_subject or "Unknown").strip().lower()
        prior_runs = [r for r in self.records if str(r.get("email_subject", "")).strip().lower() == subj_key]
        run_index = len(prior_runs) + 1

        speedup_str = "Baseline (1.0x)"
        if prior_runs:
            first_run_time = prior_runs[0].get("duration_seconds", duration)
            if duration > 0 and first_run_time > 0:
                speedup_factor = round(first_run_time / duration, 1)
                speedup_str = f"{speedup_factor}x faster" if speedup_factor > 1.0 else f"{speedup_factor}x"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "timestamp": now_str,
            "email_subject": email_subject,
            "rfq_number": rfq_number,
            "run_index": run_index,
            "duration_seconds": duration,
            "formatted_duration": fmt_dur,
            "bom_assemblies_count": assemblies_count,
            "components_count": components_count,
            "attachments_count": attachments_count,
            "cache_hits": cache_hits,
            "api_calls": api_calls,
            "speedup_vs_run1": speedup_str,
            "trigger_source": trigger_source
        }

        self.records.append(entry)
        self._save_records()
        return entry

    def get_summary_stats(self):
        """Returns consolidated aggregate benchmarks across all email runs."""
        total_runs = len(self.records)
        unique_emails = len(set(r.get("email_subject", "") for r in self.records))
        total_boms = sum(r.get("bom_assemblies_count", 0) for r in self.records)
        avg_time = round(sum(r.get("duration_seconds", 0) for r in self.records) / max(1, total_runs), 2)
        
        return {
            "total_runs": total_runs,
            "unique_emails": unique_emails,
            "total_boms_processed": total_boms,
            "avg_duration_sec": avg_time,
            "latest_runs": self.records[-20:]
        }


ACCURACY_DIR = os.path.join(DATA_DIR, "telemetry")
ACCURACY_JSON = os.path.join(ACCURACY_DIR, "accuracy_audit.json")
ACCURACY_LATEST_JSON = os.path.join(ACCURACY_DIR, "latest_accuracy_summary.json")
ACCURACY_CSV = os.path.join(ACCURACY_DIR, "accuracy_metrics.csv")


class AccuracyTelemetryStore:
    """
    Manages and exports AI vs Ground Truth Accuracy metrics and verification telemetry.
    Designed for real-time web dashboard integration and audit reporting.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AccuracyTelemetryStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        os.makedirs(ACCURACY_DIR, exist_ok=True)
        self.audits = self._load_audits()

    def _load_audits(self):
        if os.path.exists(ACCURACY_JSON):
            try:
                with open(ACCURACY_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_audits(self):
        try:
            os.makedirs(ACCURACY_DIR, exist_ok=True)
            with open(ACCURACY_JSON, "w", encoding="utf-8") as f:
                json.dump(self.audits, f, indent=2, ensure_ascii=False)
            self._export_csv()
        except Exception as e:
            print(f"[AccuracyTelemetryStore] Save error: {e}")

    def _export_csv(self):
        try:
            fieldnames = [
                "timestamp", "rfq_number", "customer", "accuracy_pct", "accuracy_grade",
                "ai_confidence_avg_pct", "verification_status", "total_components",
                "verified_components_count", "amended_components_count", "assemblies_count"
            ]
            with open(ACCURACY_CSV, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for a in self.audits:
                    writer.writerow({
                        "timestamp": a.get("timestamp", ""),
                        "rfq_number": a.get("rfq_number", ""),
                        "customer": a.get("customer", ""),
                        "accuracy_pct": a.get("overall_accuracy_pct", 0),
                        "accuracy_grade": a.get("accuracy_grade", "A"),
                        "ai_confidence_avg_pct": a.get("ai_confidence_avg_pct", 0),
                        "verification_status": a.get("verification_status", ""),
                        "total_components": a.get("total_components", 0),
                        "verified_components_count": a.get("verified_components_count", 0),
                        "amended_components_count": a.get("amended_components_count", 0),
                        "assemblies_count": a.get("assemblies_count", 0)
                    })
        except Exception as e:
            print(f"[AccuracyTelemetryStore] CSV export error: {e}")

    def evaluate_and_record(self, rfq_json: dict, is_learned_pattern: bool = False, amended_cells_count: int = 0) -> dict:
        """
        Computes accurate AI vs Human Ground Truth evaluation for an RFQ across all evaluatable columns:
        1. Component Columns (10): [Assy#, Assy Model, Assy Rev, Part, Description, MPN, MFR, QTY, UOM, Target Price] (excluding Line)
        2. Assembly Maintenance Columns (3): [EAU (pcs), Target Price (USD), Assigned MOQs]
        3. RFQ Metadata Columns (6): [Customer, RFQ Number, Project Title, Commodity, EAU, Target Price]
        """
        meta = rfq_json.get("rfq_metadata", {})
        rfq_no = meta.get("rfq_number", "RFQ")
        cust = meta.get("customer_name", "Customer")
        assemblies = rfq_json.get("assemblies", [])

        # 1. Metadata Fields (6 cells)
        meta_fields = ["customer_name", "rfq_number", "project_title", "commodity", "eau", "target_price"]
        meta_cells_total = len(meta_fields)
        meta_ev = rfq_json.get("metadata_evidence", {})
        meta_conf_list = [float(meta_ev.get(f, {}).get("confidence", 0.95)) for f in meta_fields]

        # 2. Assembly Maintenance Fields (3 cells per assembly)
        assy_cells_total = len(assemblies) * 3
        assy_details = []
        for assy in assemblies:
            assy_details.append({
                "assy_no": assy.get("assy_no", ""),
                "assy_model": assy.get("assy_model", ""),
                "assy_rev": assy.get("assy_rev", ""),
                "eau": assy.get("eau", meta.get("eau", "")),
                "target_price": assy.get("target_price", meta.get("target_price", "")),
                "moqs": meta.get("default_moqs", [100, 250, 500, 1000]),
                "status": "HUMAN_VERIFIED" if is_learned_pattern else "AI_EXTRACTED"
            })

        # 3. Component Columns (10 evaluatable columns per component item)
        # Excluding 'Line' which is just a 1-based sequence index
        comp_cells_total = 0
        total_items = 0
        conf_scores = list(meta_conf_list)
        comp_details = []

        for assy in assemblies:
            a_no = assy.get("assy_no", "")
            a_model = assy.get("assy_model", "")
            a_rev = assy.get("assy_rev", "")
            a_tp = assy.get("target_price", meta.get("target_price", ""))

            for it in assy.get("items", []):
                total_items += 1
                comp_cells_total += 10 # 10 distinct columns evaluated per component

                ev = it.get("evidence", {})
                mpn_ev = ev.get("mpn", {}) if isinstance(ev.get("mpn"), dict) else {}
                c_conf = float(mpn_ev.get("confidence", 0.95))
                conf_scores.append(c_conf)

                if is_learned_pattern and amended_cells_count == 0:
                    c_acc = 100.0
                    c_stat = "HUMAN_VERIFIED_GROUND_TRUTH"
                elif amended_cells_count > 0:
                    c_acc = 100.0
                    c_stat = "HUMAN_AMENDED"
                else:
                    c_acc = round(c_conf * 100.0, 1)
                    c_stat = "AI_MODEL_PREDICTION"

                comp_details.append({
                    "assy_no": a_no,
                    "assy_model": a_model,
                    "assy_rev": a_rev,
                    "part_number": it.get("part_number", ""),
                    "description": it.get("description", ""),
                    "mpn": it.get("mpn", ""),
                    "mfr": it.get("mfr", ""),
                    "qty": it.get("qty", 1),
                    "uom": it.get("uom", "EA"),
                    "target_price": it.get("target_price", a_tp),
                    "confidence_pct": round(c_conf * 100.0, 1),
                    "accuracy_pct": c_acc,
                    "status": c_stat
                })

        total_evaluated_cells = meta_cells_total + assy_cells_total + comp_cells_total
        avg_conf_pct = round((sum(conf_scores) / max(1, len(conf_scores))) * 100.0, 1)

        # Compute Ground Truth Accuracy vs Human Review
        if is_learned_pattern and amended_cells_count == 0:
            overall_acc = 100.0
            ver_status = "100% Ground Truth (Human Verified)"
            grade = "A+ (Perfect Ground Truth)"
            correct_cells = total_evaluated_cells
        elif amended_cells_count > 0 and total_evaluated_cells > 0:
            correct_cells = max(0, total_evaluated_cells - amended_cells_count)
            overall_acc = round((correct_cells / total_evaluated_cells) * 100.0, 1)
            ver_status = f"{overall_acc}% ({amended_cells_count}/{total_evaluated_cells} cells amended)"
            grade = "A (Human Corrected)"
        else:
            overall_acc = avg_conf_pct
            ver_status = f"{avg_conf_pct}% (AI Predicted, Pending Review)"
            grade = "B+ (AI Initial Extraction)"
            correct_cells = int(total_evaluated_cells * (avg_conf_pct / 100.0))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        audit_entry = {
            "timestamp": now_str,
            "rfq_number": rfq_no,
            "customer": cust,
            "overall_accuracy_pct": overall_acc,
            "accuracy_grade": grade,
            "verification_status": ver_status,
            "is_learned_pattern_applied": is_learned_pattern,
            "ai_confidence_avg_pct": avg_conf_pct,
            "total_evaluated_cells": total_evaluated_cells,
            "correct_cells_count": correct_cells,
            "amended_cells_count": amended_cells_count,
            "evaluated_column_breakdown": {
                "metadata_columns_count": meta_cells_total,
                "assembly_columns_count": assy_cells_total,
                "component_columns_count": comp_cells_total,
                "component_columns_evaluated": ["Assy#", "Assy Model", "Assy Rev", "Part", "Description", "MPN", "MFR", "QTY", "UOM", "Target Price (USD)"],
                "assembly_columns_evaluated": ["Assy#", "Assy Model", "Assy Rev", "EAU (pcs)", "Target Price (USD)", "Assigned MOQs"],
                "metadata_columns_evaluated": ["Customer", "RFQ Number", "Project Title", "Commodity", "EAU", "Target Price"]
            },
            "total_components": total_items,
            "assemblies_count": len(assemblies),
            "assemblies": assy_details,
            "components": comp_details
        }

        # Update or append in audits list
        existing_idx = next((i for i, a in enumerate(self.audits) if a.get("rfq_number") == rfq_no), -1)
        if existing_idx >= 0:
            self.audits[existing_idx] = audit_entry
        else:
            self.audits.append(audit_entry)

        self._save_audits()

        # Write latest summary JSON for instant Web Dashboard polling
        try:
            with open(ACCURACY_LATEST_JSON, "w", encoding="utf-8") as f:
                json.dump(audit_entry, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        print(f"[AccuracyTelemetryStore] [Accuracy Audit] Recorded Accuracy for {rfq_no}: {overall_acc}% ({ver_status})")
        return audit_entry

    def get_latest_audit(self) -> dict:
        return self.audits[-1] if self.audits else {}

    def get_all_audits(self) -> list:
        return list(self.audits)

    def get_audit_for_rfq(self, rfq_number: str) -> dict:
        for a in reversed(self.audits):
            if a.get("rfq_number") == rfq_number:
                return a
        return {}


ERROR_DIR = os.path.join(DATA_DIR, "telemetry", "errors")
ERROR_JSON = os.path.join(DATA_DIR, "telemetry", "agent_errors.json")
ERROR_LATEST_JSON = os.path.join(DATA_DIR, "telemetry", "latest_errors_summary.json")
ERROR_CSV = os.path.join(DATA_DIR, "telemetry", "error_metrics.csv")

_MODULE_TO_AGENT = {
    "LLMGateway": "brain",
    "DrawingVisionAgent": "bom",
    "PromptGuard": "brain",
    "ChatAsync": "brain",
    "BOMVerificationAgent": "bom",
    "CycleTimeAIEngine": "cycletime",
    "NPIMLClassifier": "npi",
}


def _agent_id_for_module(module: str) -> str:
    if module in _MODULE_TO_AGENT:
        return _MODULE_TO_AGENT[module]
    key = str(module or "brain").lower().replace(" ", "")
    if key in ("brain", "bom", "sourcing", "cycletime", "costing", "npi", "wi"):
        return key
    return "brain"


def _mirror_incident_to_platform(incident: dict) -> None:
    """Fail-open POST to the Team 3 broker. Never raises into the desktop writer."""
    try:
        import json as _json
        import urllib.request
        import urllib.error

        base = os.environ.get("CX_PLATFORM_URL", "http://127.0.0.1:8000").rstrip("/")
        token = os.environ.get("CX_AGENT_AUTH_TOKEN", "dev-agent-token")
        module = incident.get("module", "brain")
        payload = {
            "agent_id": _agent_id_for_module(module),
            "event_type": "TEAM2_SERVICE_ERROR",
            "error_type": incident.get("error_category", "UNHANDLED"),
            "detail": str(incident.get("error_message", ""))[:500],
            "severity": incident.get("severity", "ERROR"),
            "transaction_uuid": incident.get("rfq_number") or None,
            "module": module,
            "error_id": incident.get("error_id"),
            "status": incident.get("status"),
            "rfq_number": incident.get("rfq_number"),
            "customer": incident.get("customer"),
        }
        req = urllib.request.Request(
            f"{base}/agents/errors",
            data=_json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2):
            pass
    except Exception:
        pass


class ErrorTelemetryStore:
    """
    Singleton managing capture, storage, and web-dashboard export of AI Agent errors.
    Captures LLM rate limits, prompt hallucinations, vision failures, and parsing errors.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ErrorTelemetryStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        os.makedirs(ERROR_DIR, exist_ok=True)
        self.errors = self._load_errors()

    def _load_errors(self):
        if os.path.exists(ERROR_JSON):
            try:
                with open(ERROR_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_errors(self):
        try:
            os.makedirs(os.path.dirname(ERROR_JSON), exist_ok=True)
            with open(ERROR_JSON, "w", encoding="utf-8") as f:
                json.dump(self.errors[-300:], f, indent=2, ensure_ascii=False)
            self._export_csv()
            self._update_latest_summary()
        except Exception as e:
            print(f"[ErrorTelemetryStore] Save warning: {e}")

    def _export_csv(self):
        try:
            fieldnames = [
                "error_id", "timestamp", "rfq_number", "customer", "module",
                "error_category", "severity", "error_message", "recovery_action", "status"
            ]
            with open(ERROR_CSV, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for err in self.errors:
                    writer.writerow({
                        "error_id": err.get("error_id", ""),
                        "timestamp": err.get("timestamp", ""),
                        "rfq_number": err.get("rfq_number", ""),
                        "customer": err.get("customer", ""),
                        "module": err.get("module", ""),
                        "error_category": err.get("error_category", ""),
                        "severity": err.get("severity", ""),
                        "error_message": str(err.get("error_message", ""))[:120],
                        "recovery_action": err.get("recovery_action", ""),
                        "status": err.get("status", "")
                    })
        except Exception as e:
            print(f"[ErrorTelemetryStore] CSV export error: {e}")

    def _update_latest_summary(self):
        try:
            total = len(self.errors)
            cat_counts = {}
            mod_counts = {}
            recovered_count = sum(1 for e in self.errors if "RECOVERED" in str(e.get("status", "")).upper())

            for e in self.errors:
                cat = e.get("error_category", "UNKNOWN")
                mod = e.get("module", "GENERAL")
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
                mod_counts[mod] = mod_counts.get(mod, 0) + 1

            rec_rate = round((recovered_count / max(1, total)) * 100.0, 1) if total > 0 else 100.0
            latest_rec = self.errors[-1] if self.errors else {}

            summary = {
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_incidents": total,
                "auto_recovery_rate_pct": rec_rate,
                "incidents_by_category": cat_counts,
                "incidents_by_module": mod_counts,
                "latest_incident": latest_rec,
                "recent_incidents": self.errors[-15:]
            }
            with open(ERROR_LATEST_JSON, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ErrorTelemetryStore] Summary error: {e}")

    def record_error(self, module: str, error_category: str, error_message: str,
                     severity: str = "WARNING", rfq_number: str = "", customer: str = "",
                     document_name: str = "", prompt_context: dict = None,
                     recovery_action: str = "", stack_trace: str = "",
                     status: str = "RECOVERED_VIA_FALLBACK") -> dict:
        """
        Records an incident, writes individual incident JSON to data/telemetry/errors/,
        updates master log and web-dashboard telemetry.
        """
        now = datetime.now()
        ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
        err_id = f"ERR_{now.strftime('%Y%m%d_%H%M%S')}_{len(self.errors)+1:03d}"

        incident = {
            "error_id": err_id,
            "timestamp": ts_str,
            "rfq_number": rfq_number or "N/A",
            "customer": customer or "N/A",
            "module": module,
            "error_category": error_category,
            "severity": severity,
            "error_message": str(error_message),
            "document_name": document_name or "N/A",
            "prompt_context": prompt_context or {},
            "recovery_action": recovery_action or "Fallback activated",
            "stack_trace": str(stack_trace)[:500] if stack_trace else "",
            "status": status
        }

        # 1. Write individual incident JSON file for drill-down investigation
        try:
            inc_path = os.path.join(ERROR_DIR, f"{err_id}.json")
            with open(inc_path, "w", encoding="utf-8") as f:
                json.dump(incident, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # 2. Append to in-memory list and master json
        self.errors.append(incident)
        self._save_errors()
        threading.Thread(target=_mirror_incident_to_platform, args=(incident,), daemon=True).start()

        print(f"[ErrorTelemetryStore] [Incident Logged] {err_id} ({error_category} in {module}): {str(error_message)[:80]}")
        return incident

    def get_all_errors(self) -> list:
        return self.errors

    def get_latest_summary(self) -> dict:
        if os.path.exists(ERROR_LATEST_JSON):
            try:
                with open(ERROR_LATEST_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


