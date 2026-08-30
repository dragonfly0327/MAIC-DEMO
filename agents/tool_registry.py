# ==============================================================================
# --- ContinuumX Authoritative Agent Tool Registry ---
# Exhaustive registry wrapping ALL ContinuumX subsystem tools & functions across:
#   1. BOM Verification & Sourcing Wizard (ref/BOM)
#   2. Sourcing Engine & Quote Optimization (ref/Sourcing)
#   3. Cycle Time & NRE Model (ref/Cycle Time)
#   4. Costing & Quotation Calculation (ref/Costing)
#   5. NPI Project Turn-on & RPN Engine (ref/NPI)
#   6. Work Instruction Engineering & Macro (ref/WI)
#   7. Central Project Management & Revert Engine (ref/Project Management)
# ==============================================================================

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("ContinuumX.ToolRegistry")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ToolDefinition:
    """Metadata descriptor for an Agent Tool."""
    def __init__(
        self,
        name: str,
        description: str,
        system: str,
        inputs: Dict[str, Any],
        output: str,
        requires: List[str],
        side_effects: List[str],
        human_approval: bool,
        risk: str,
        existing_function: str,
        category: str  # "READ_ONLY", "AUTOMATIC_ACTION", "HUMAN_APPROVAL", "CONDITIONAL_DISPATCH", "HIGH_RISK"
    ):
        self.name = name
        self.description = description
        self.system = system
        self.inputs = inputs
        self.output = output
        self.requires = requires
        self.side_effects = side_effects
        self.human_approval = human_approval
        self.risk = risk
        self.existing_function = existing_function
        self.category = category

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "system": self.system,
            "inputs": self.inputs,
            "output": self.output,
            "requires": self.requires,
            "side_effects": self.side_effects,
            "human_approval": self.human_approval,
            "risk": self.risk,
            "existing_function": self.existing_function,
            "category": self.category
        }


class ContinuumXToolRegistry:
    """
    Authoritative Agent Tool Registry wrapping existing microservice functions.
    Preserves existing subsystems as the single source of truth.
    """

    @classmethod
    def get_all_tool_definitions(cls) -> Dict[str, ToolDefinition]:
        """Returns the dictionary of all registered tool metadata across all systems."""
        defs = [
            # ==================================================================
            # 1. BOM SYSTEM TOOLS (ref/BOM)
            # ==================================================================
            ToolDefinition(
                name="bom.get_status",
                description="Retrieve lifecycle status, assemblies, and MOQs for an RFQ from the BOM database.",
                system="BOM",
                inputs={"rfq_id": "string"},
                output="Dict with RFQ status, Customer, Global MOQs, and Assembly list",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.BOM.utils.BOM_DATA_DIR JSON read",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="bom.get_data",
                description="Read full verified BOM line items, components, and MPN mappings.",
                system="BOM",
                inputs={"rfq_id": "string"},
                output="Dict containing complete raw_data JSON with line items",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.BOM.bomprocessor.DataLoader",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="bom.auto_verify",
                description="RPA action: Ingests raw customer Excel BOM, auto-maps columns, and sets Global MOQs.",
                system="BOM",
                inputs={"excel_path": "string", "customer": "string", "rfq_id": "string", "moqs": "list[int]"},
                output="Tuple(bool success, str message)",
                requires=["valid_excel_file"],
                side_effects=["Creates verified BOM JSON in BOM Data/"],
                human_approval=False,
                risk="medium",
                existing_function="ref.BOM.bomformatter.verify_bom_workflow",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="bom.open_review_window",
                description="Opens the exact BOM Verification & MOQ Maintenance window (Gate 1) for user sign-off.",
                system="BOM",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["rfq_exists"],
                side_effects=["Launches ref/BOM UI window"],
                human_approval=True,
                risk="low",
                existing_function="ref.BOM.bomformatter.assign_moq_workflow",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="bom.open_target_price_window",
                description="Opens Target Price & EAU Maintenance dialog for user input.",
                system="BOM",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["rfq_exists"],
                side_effects=["Launches TargetPriceEAUPanel"],
                human_approval=True,
                risk="low",
                existing_function="ref.BOM.main.input_target_price_workflow",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="bom.open_alt_mpn_maint",
                description="Opens Customer Alternative MPN Maintenance dialog.",
                system="BOM",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches AlternativeMPNMaintenanceDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.BOM.main.open_alt_mpn_maint",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="bom.open_uom_maint",
                description="Opens Unit of Measurement (UOM) Conversion Maintenance dialog.",
                system="BOM",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches UOMConversionDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.BOM.main.open_uom_conversion_maint",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="bom.execute_system_dispatch",
                description="Robotic Dispatch: Checks existing BOM dispatch window filter. If eligible, executes existing dispatch function.",
                system="BOM",
                inputs={"rfq_id": "string", "username": "string", "comments": "string"},
                output="Tuple(bool success, str message)",
                requires=["system_dispatch_eligible"],
                side_effects=["Sends real email, advances stage to pending_sourcing_and_cycle_time, logs history"],
                human_approval=False,
                risk="medium",
                existing_function="ref.BOM.bomformatter.dispatch_rfq_workflow",
                category="CONDITIONAL_DISPATCH"
            ),

            # ==================================================================
            # 2. SOURCING SYSTEM TOOLS (ref/Sourcing)
            # ==================================================================
            ToolDefinition(
                name="sourcing.get_status",
                description="Check sourcing calculation completion status and assigned winning suppliers.",
                system="Sourcing",
                inputs={"rfq_id": "string"},
                output="Dict with sourcing_status, winning suppliers, and excess costs",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Sourcing.bomformatter.load_saved_calculations",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="sourcing.get_results",
                description="Return calculated winning MPNs, prices, and MOQ excess details.",
                system="Sourcing",
                inputs={"rfq_id": "string"},
                output="Dict with winning parts, suppliers, and excess costs",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Sourcing.sourcing_engine.SourcingEngine.process_all",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="sourcing.auto_calculate",
                description="RPA action: Runs Total Usage Sourcing calculations across all assemblies in the background.",
                system="Sourcing",
                inputs={"rfq_id": "string", "calc_mode": "string (default: 'total_usage')"},
                output="Tuple(bool success, str message)",
                requires=["bom_verified"],
                side_effects=["Computes winning MPNs and saves sourcing calculations"],
                human_approval=False,
                risk="medium",
                existing_function="ref.Sourcing.sourcing_engine.SourcingEngine.process_all",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="sourcing.open_review_window",
                description="Opens the exact Sourcing Master Workflow Calculation Review window (Gate 2) for user sign-off.",
                system="Sourcing",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["sourcing_started"],
                side_effects=["Launches ref/Sourcing UI window"],
                human_approval=True,
                risk="low",
                existing_function="ref.Sourcing.sourcing_ui.SourcingUI",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="sourcing.approve_calculations",
                description="Approves calculated sourcing results, sets sourcing_status to completed.",
                system="Sourcing",
                inputs={"rfq_id": "string"},
                output="Tuple(bool success, str message)",
                requires=["sourcing_calculated"],
                side_effects=["Sets sourcing_status='completed' in RFQ JSON"],
                human_approval=True,
                risk="low",
                existing_function="ref.Sourcing.sourcing_ui.SourcingUI.approve",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="sourcing.export_excel",
                description="Exports full multi-tab Sourcing Excel workbook.",
                system="Sourcing",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["sourcing_calculated"],
                side_effects=["Writes Excel workbook to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Sourcing.bomprocessor.export_sourcing_to_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="sourcing.export_missing_report",
                description="Exports Missing Sourcing Quotes report.",
                system="Sourcing",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["sourcing_calculated"],
                side_effects=["Writes Missing Quotes Excel to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Sourcing.bomprocessor.export_missing_sourcing_to_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="sourcing.toggle_consign",
                description="Toggles consignment flag for selected part items (sets unit cost to $0.00).",
                system="Sourcing",
                inputs={"rfq_id": "string", "part_numbers": "list[str]", "is_consign": "bool"},
                output="Tuple(bool success, str message)",
                requires=["sourcing_loaded"],
                side_effects=["Updates part consignment state in sourcing model"],
                human_approval=False,
                risk="low",
                existing_function="ref.Sourcing.sourcing_ui.SourcingUI.toggle_consign_item",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="sourcing.open_sourcing_maint",
                description="Opens Sourcing Master Data Management window.",
                system="Sourcing",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches SourcingMasterDataWindow"],
                human_approval=True,
                risk="low",
                existing_function="ref.Sourcing.main.open_sourcing_maint",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="sourcing.manage_currency_config",
                description="Opens Currency & Markup Configuration dialog.",
                system="Sourcing",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches CurrencyMarkupConfigDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.Sourcing.main._manage_currency_config",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="sourcing.execute_system_dispatch",
                description="Robotic Dispatch: Checks existing Sourcing dispatch filter. If eligible, executes existing dispatch function.",
                system="Sourcing",
                inputs={"rfq_id": "string", "username": "string", "comments": "string"},
                output="Tuple(bool success, str message)",
                requires=["system_dispatch_eligible"],
                side_effects=["Sends real email, advances stage to pending_costing, logs history"],
                human_approval=False,
                risk="medium",
                existing_function="ref.Sourcing.bomformatter.dispatch_sourcing_workflow",
                category="CONDITIONAL_DISPATCH"
            ),

            # ==================================================================
            # 3. CYCLE TIME SYSTEM TOOLS (ref/Cycle Time)
            # ==================================================================
            ToolDefinition(
                name="cycle_time.get_status",
                description="Check cycle time completion and inspect calculated seconds per assembly.",
                system="Cycle Time",
                inputs={"rfq_id": "string"},
                output="Dict with cycle_time_status and process rates per assembly",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Cycle Time.cycle_time_model.CycleTimeModel",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="cycle_time.ai_extract_drawing",
                description="RPA action: Extracts wire specs and complexity from drawing to compute and pre-fill cycle times.",
                system="Cycle Time",
                inputs={"drawing_path": "string", "rfq_id": "string", "assy_code": "string"},
                output="Dict with extracted AWG, length, circuits, and proposed cycle times",
                requires=["drawing_available"],
                side_effects=["Pre-populates Cycle Time process table"],
                human_approval=False,
                risk="medium",
                existing_function="agents.orchestrator.cycle_time_ai.CycleTimeAIEngine.analyze_drawing",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="cycle_time.open_review_window",
                description="Opens the exact Cycle Time Maintenance window (Gate 3) with pre-filled AI rates for user sign-off.",
                system="Cycle Time",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["rfq_exists"],
                side_effects=["Launches ref/Cycle Time UI window"],
                human_approval=True,
                risk="low",
                existing_function="ref.Cycle Time.cycle_time_page.CycleTimeMaintenanceWindow",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="cycle_time.save_cycle_times",
                description="Saves cycle times and sets cycle_time_status to completed.",
                system="Cycle Time",
                inputs={"rfq_id": "string", "assembly_code": "string", "process_rows": "list[dict]"},
                output="Tuple(bool success, str message)",
                requires=["rfq_exists"],
                side_effects=["Sets cycle_time_status='completed' in RFQ JSON"],
                human_approval=True,
                risk="low",
                existing_function="ref.Cycle Time.cycle_time_model.CycleTimeModel.save_assembly_cycle_time",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="cycle_time.manage_nre",
                description="Opens NRE Tooling & Fixture assignment dialog.",
                system="Cycle Time",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["rfq_exists"],
                side_effects=["Launches NREMaintenanceDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.Cycle Time.cycle_time_page.open_nre_dialog",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="cycle_time.export_excel",
                description="Exports Cycle Time calculation sheet to Excel.",
                system="Cycle Time",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["cycle_time_calculated"],
                side_effects=["Writes Cycle Time Excel to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Cycle Time.utils.export_cycle_time_to_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="cycle_time.open_master_maint",
                description="Opens Cycle Time, NRE & Currency Master Maintenance window.",
                system="Cycle Time",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches CycleTimeMasterMaintenanceDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.Cycle Time.main.open_master_maint",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="cycle_time.execute_system_dispatch",
                description="Robotic Dispatch: Checks existing Cycle Time dispatch filter. If eligible, executes existing dispatch function.",
                system="Cycle Time",
                inputs={"rfq_id": "string", "username": "string", "comments": "string"},
                output="Tuple(bool success, str message)",
                requires=["system_dispatch_eligible"],
                side_effects=["Sends real email, marks cycle_time_status completed, logs history"],
                human_approval=False,
                risk="medium",
                existing_function="ref.Cycle Time.main.DispatchSelectionDialog.dispatch_handler",
                category="CONDITIONAL_DISPATCH"
            ),

            # ==================================================================
            # 4. COSTING SYSTEM TOOLS (ref/Costing)
            # ==================================================================
            ToolDefinition(
                name="costing.get_summary",
                description="Read final quotation summary metrics: Gross Margin %, EAU Revenue, and Base Unit Prices.",
                system="Costing",
                inputs={"rfq_id": "string"},
                output="Dict with executive costing metrics, margins, and breakdown",
                requires=["costing_calculated"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Costing.summary_table_page.SummaryTablePage",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="costing.auto_calculate_quotation",
                description="RPA action: Merges winning Sourcing + Cycle Time data and computes full quotation matrix.",
                system="Costing",
                inputs={"rfq_id": "string"},
                output="Tuple(bool success, str message)",
                requires=["sourcing_completed", "cycle_time_completed"],
                side_effects=["Generates draft quotation in Saved Quotations/"],
                human_approval=False,
                risk="medium",
                existing_function="ref.Costing.costing_model.CostingModel.calculate_unit_price",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="costing.open_review_window",
                description="Opens the exact Detailed Costing Calculation window (Gate 4) for user review.",
                system="Costing",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["costing_started"],
                side_effects=["Launches ref/Costing UI window"],
                human_approval=True,
                risk="low",
                existing_function="ref.Costing.detailed_costing_page.DetailedCostingPage",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="costing.open_summary_approval",
                description="Opens the Costing Summary for Approval Page (Gate 5 prerequisite).",
                system="Costing",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["costing_saved"],
                side_effects=["Launches SummaryTablePage"],
                human_approval=True,
                risk="low",
                existing_function="ref.Costing.main.SummaryTablePage",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="costing.open_approval_composer",
                description="Opens the exact Email Notification Composer window (Gate 5) to send executive approval request.",
                system="Costing",
                inputs={"rfq_id": "string"},
                output="bool indicating whether window opened",
                requires=["costing_saved"],
                side_effects=["Renders EmailComposerDialog modal"],
                human_approval=True,
                risk="low",
                existing_function="ref.Costing.summary_table_page.SummaryTablePage._on_send_approval_email",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="costing.export_calc_details",
                description="Exports calculation details multi-tab Excel workbook.",
                system="Costing",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["costing_calculated"],
                side_effects=["Writes Excel calculation details to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Costing.excel_exporter_details.export_calc_details",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="costing.export_summary_excel",
                description="Exports quotation summary Excel workbook.",
                system="Costing",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["costing_calculated"],
                side_effects=["Writes Summary Excel to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Costing.excel_exporter.export_summary_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="costing.export_summary_pdf",
                description="Exports executive summary customer quotation PDF.",
                system="Costing",
                inputs={"rfq_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["costing_calculated"],
                side_effects=["Writes Quotation PDF to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Costing.pdf_summary_exporter.export_summary_pdf",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="costing.open_commodity_config",
                description="Opens Commodity Configuration dialog.",
                system="Costing",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches CommodityConfigDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.Costing.main._open_commodity_config",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="costing.open_quotation_remarks",
                description="Opens Quotation Remarks Editor by Commodity.",
                system="Costing",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches QuotationRemarksDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.Costing.main._open_quotation_remarks",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="costing.execute_system_dispatch",
                description="Robotic Dispatch: Checks existing Costing dispatch filter. If eligible, executes existing dispatch function.",
                system="Costing",
                inputs={"rfq_id": "string", "username": "string", "comments": "string"},
                output="Tuple(bool success, str message)",
                requires=["system_dispatch_eligible"],
                side_effects=["Sends real email, advances stage to pending_npi, logs history"],
                human_approval=False,
                risk="medium",
                existing_function="ref.Costing.main.CostingAnalysisWindow._open_dispatch_rfq",
                category="CONDITIONAL_DISPATCH"
            ),

            # ==================================================================
            # 5. NPI SYSTEM TOOLS (ref/NPI)
            # ==================================================================
            ToolDefinition(
                name="npi.get_dashboard",
                description="Read active NPI project turn-on dashboard and component risk batches.",
                system="NPI",
                inputs={},
                output="Dict with active project batches, RPN status, and progress",
                requires=[],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.NPI.project_turnon_ui.NPIProjectDashboardFrame",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="npi.award_project",
                description="Awards new project batch from Costing RFQ and Customer PO Number.",
                system="NPI",
                inputs={"rfq_id": "string", "customer": "string", "po_number": "string"},
                output="Tuple(bool success, str batch_id)",
                requires=["costing_dispatched"],
                side_effects=["Creates project batch in npi_projects.json"],
                human_approval=True,
                risk="medium",
                existing_function="ref.NPI.project_turnon_ui.on_award_project",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="npi.rpn_evaluate",
                description="Evaluates RPN component risk scores (1-100) using NPIRPNEngine.",
                system="NPI",
                inputs={"batch_id": "string"},
                output="Dict with component risk scores, lead time risk, and supplier ratings",
                requires=["batch_exists"],
                side_effects=["Updates RPN scores in batch record"],
                human_approval=False,
                risk="low",
                existing_function="ref.NPI.npi_rpn_engine.NPIRPNEngine.evaluate_batch",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="npi.ml_classify",
                description="Runs ML classifier to categorize components into commodity classes (ACCS, RESI, etc.).",
                system="NPI",
                inputs={"mpn": "string", "description": "string"},
                output="Dict with predicted commodity category and confidence",
                requires=[],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.NPI.npi_ml_classifier.NPIMLClassifier.predict",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="npi.open_dashboard_window",
                description="Opens NPI Project Dashboard window.",
                system="NPI",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches ref/NPI UI window"],
                human_approval=True,
                risk="low",
                existing_function="ref.NPI.main.NPIProjectDashboardFrame",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="npi.open_verification_grid",
                description="Opens MPN Final Verification Grid window.",
                system="NPI",
                inputs={"batch_id": "string"},
                output="bool indicating whether window opened",
                requires=["batch_exists"],
                side_effects=["Launches VerificationGridFrame"],
                human_approval=True,
                risk="low",
                existing_function="ref.NPI.main.VerificationGridFrame",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="npi.export_rpn_excel",
                description="Exports RPN Classification report to Excel.",
                system="NPI",
                inputs={"batch_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["batch_exists"],
                side_effects=["Writes RPN Excel to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.NPI.utils.export_rpn_to_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="npi.dispatch_to_wi",
                description="Dispatches awarded NPI batch to Work Instruction (WI) stage.",
                system="NPI",
                inputs={"batch_id": "string", "username": "string"},
                output="Tuple(bool success, str message)",
                requires=["npi_verified"],
                side_effects=["Advances status to pending_wi, sends email to WI team"],
                human_approval=True,
                risk="medium",
                existing_function="ref.NPI.project_turnon_ui.handover_to_wi",
                category="CONDITIONAL_DISPATCH"
            ),

            # ==================================================================
            # 6. WORK INSTRUCTION SYSTEM TOOLS (ref/WI)
            # ==================================================================
            ToolDefinition(
                name="wi.get_drafts",
                description="Lists all active Work Instruction drafts and lifecycle status.",
                system="WI",
                inputs={"filter_status": "string (optional)"},
                output="List of draft WI records",
                requires=[],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.WI.ui.dialogs.DraftSelectorDialog",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="wi.create_new",
                description="Initializes a new Work Instruction draft for an assembly.",
                system="WI",
                inputs={"customer": "string", "rfq_id": "string", "assembly_code": "string"},
                output="Tuple(bool success, str draft_id)",
                requires=[],
                side_effects=["Creates initial draft JSON in DRAFT WI/"],
                human_approval=False,
                risk="low",
                existing_function="ref.WI.ui.pages.router._open_new_wi_flow",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="wi.open_editor_window",
                description="Opens Work Instruction Visual Layout Editor.",
                system="WI",
                inputs={"draft_id": "string"},
                output="bool indicating whether window opened",
                requires=["draft_exists"],
                side_effects=["Launches WorkInstructionEditor window"],
                human_approval=True,
                risk="low",
                existing_function="ref.WI.ui.pages.editor.WorkInstructionEditor",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="wi.save_draft",
                description="Saves WI visual layout and process sequence JSON.",
                system="WI",
                inputs={"draft_id": "string", "layout_data": "dict"},
                output="Tuple(bool success, str message)",
                requires=["draft_exists"],
                side_effects=["Writes JSON to DRAFT WI/"],
                human_approval=False,
                risk="low",
                existing_function="ref.WI.core.DataStore.save_draft_wi",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="wi.submit_review",
                description="Submits Work Instruction draft to Pending Review status.",
                system="WI",
                inputs={"draft_id": "string", "username": "string"},
                output="Tuple(bool success, str message)",
                requires=["draft_exists"],
                side_effects=["Sets status to 'Pending Review', sends email to reviewer"],
                human_approval=True,
                risk="low",
                existing_function="ref.WI.ui.pages.editor.submit_for_review",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="wi.approve_wi",
                description="Approves Work Instruction draft with reviewer digital signature.",
                system="WI",
                inputs={"draft_id": "string", "username": "string", "signature_path": "string"},
                output="Tuple(bool success, str message)",
                requires=["draft_in_review"],
                side_effects=["Sets status to 'Approved', stamps signature"],
                human_approval=True,
                risk="medium",
                existing_function="ref.WI.ui.pages.editor.approve_wi",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="wi.export_macro_excel",
                description="Generates official formatted macro-enabled Excel (.xlsm) Work Instruction workbook.",
                system="WI",
                inputs={"draft_id": "string", "output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=["draft_approved"],
                side_effects=["Generates .xlsm file in WI_Log/"],
                human_approval=True,
                risk="low",
                existing_function="ref.WI.macro.MacroRunner.generate_wi_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="wi.open_process_maint",
                description="Opens Process Code Maintenance dialog.",
                system="WI",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches ProcessMaintenanceDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.WI.ui.pages.router._open_process_maintenance",
                category="HUMAN_APPROVAL"
            ),
            ToolDefinition(
                name="wi.open_signature_maint",
                description="Opens User Digital Signature Maintenance dialog.",
                system="WI",
                inputs={},
                output="bool indicating whether window opened",
                requires=[],
                side_effects=["Launches SignatureMaintenanceDialog"],
                human_approval=True,
                risk="low",
                existing_function="ref.WI.ui.pages.router._open_signature_maintenance",
                category="HUMAN_APPROVAL"
            ),

            # ==================================================================
            # 7. PROJECT MANAGEMENT & REVERT TOOLS (ref/Project Management)
            # ==================================================================
            ToolDefinition(
                name="project.get_history",
                description="Retrieve audit trail, timestamped history, and revert history for an RFQ.",
                system="Project Management",
                inputs={"rfq_id": "string"},
                output="List of timestamped audit trail records",
                requires=["rfq_exists"],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Project Management.revert_workflow.resolve_bom_filepath",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="project.get_treeview_data",
                description="Reads the complete 14-column project management status table across all RFQs.",
                system="Project Management",
                inputs={},
                output="List of 14-column RFQ status tuples",
                requires=[],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Project Management.base_panel.BaseProjectManagementPanel",
                category="READ_ONLY"
            ),
            ToolDefinition(
                name="project.revert",
                description="Executes project revert: calls request_revert(), resets downstream sub-statuses, resurrects BOM session, sends revert email.",
                system="Project Management",
                inputs={"rfq_id": "string", "customer": "string", "target_stage": "string", "reason": "string", "requested_by": "string"},
                output="Tuple(bool success, str message)",
                requires=["rfq_exists"],
                side_effects=["Modifies status, creates revert_pending, resets downstream flags, sends revert email"],
                human_approval=True,
                risk="high",
                existing_function="ref.Project Management.revert_workflow.request_revert",
                category="HIGH_RISK"
            ),
            ToolDefinition(
                name="project.send_stuck_query",
                description="Sends inquiry notification email for stalled RFQs to the current stage PIC.",
                system="Project Management",
                inputs={"rfq_id": "string", "sender": "string", "notes": "string"},
                output="Tuple(bool success, str message)",
                requires=["rfq_exists"],
                side_effects=["Sends SMTP inquiry email, logs query in audit history"],
                human_approval=True,
                risk="low",
                existing_function="ref.Project Management.dialogs.StuckQueryEmailDialog",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="project.export_excel",
                description="Exports the 14-column Project Management status overview to Excel.",
                system="Project Management",
                inputs={"output_path": "string"},
                output="Tuple(bool success, str path)",
                requires=[],
                side_effects=["Writes PM Overview Excel to disk"],
                human_approval=False,
                risk="low",
                existing_function="ref.Project Management.main.export_pm_excel",
                category="AUTOMATIC_ACTION"
            ),
            ToolDefinition(
                name="system.get_pics",
                description="Resolve configured Stage PIC names and email addresses from system_pics.json.",
                system="System",
                inputs={"stage_code": "string"},
                output="Dict with 'to' and 'cc' recipient lists",
                requires=[],
                side_effects=[],
                human_approval=False,
                risk="low",
                existing_function="ref.Project Management.revert_workflow.get_system_pics",
                category="READ_ONLY"
            )
        ]
        return {d.name: d for d in defs}

    # ==========================================================================
    # TOOL ELIGIBILITY CHECKER
    # ==========================================================================

    @classmethod
    def check_tool_eligibility(cls, tool_name: str, rfq_id: str, username: str = "ContinuumX Agent") -> Tuple[bool, str]:
        """
        Validates if a tool can be executed right now for an RFQ based on live system state.
        Returns Tuple(is_eligible, reason_if_not_eligible).
        """
        tools = cls.get_all_tool_definitions()
        tool_def = tools.get(tool_name)
        if not tool_def:
            return False, f"Tool '{tool_name}' is not registered in ContinuumX Tool Registry."

        from agents.workflow_state import WorkflowStateManager
        state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)

        # 1. RFQ existence check
        if not state.get("exists") and tool_name not in ("bom.auto_verify", "system.get_pics", "npi.get_dashboard", "wi.get_drafts", "project.get_treeview_data"):
            return False, f"RFQ '{rfq_id}' does not exist in the BOM database."

        # 2. Session lock check
        if state.get("is_locked") and state.get("locked_by") != username:
            return False, f"RFQ '{rfq_id}' is currently locked by human user: {state.get('locked_by')}."

        # 3. Category-specific eligibility
        if tool_def.category == "CONDITIONAL_DISPATCH":
            dept = tool_name.split(".")[0]  # e.g. "bom", "sourcing", "cycle_time", "costing", "npi"
            eligible_dispatches = state.get("system_eligible_dispatches", [])
            if dept not in eligible_dispatches:
                return False, f"RFQ '{rfq_id}' is not eligible for {dept} dispatch under existing system rules."

        return True, "Eligible"

    # ==========================================================================
    # TOOL WRAPPER EXECUTION METHODS
    # ==========================================================================

    @classmethod
    def _ensure_module_path(cls, module_name: str) -> str:
        target_dir = os.path.normpath(os.path.join(BASE_DIR, "ref", module_name))
        if os.path.exists(target_dir) and target_dir not in sys.path:
            sys.path.append(target_dir)
        return target_dir

    @classmethod
    def get_bom_status(cls, rfq_id: str) -> Dict[str, Any]:
        from agents.workflow_state import WorkflowStateManager
        return WorkflowStateManager.get_rfq_workflow_state(rfq_id)

    @classmethod
    def execute_system_dispatch(
        cls,
        dept: str,
        rfq_id: str,
        username: str = "ContinuumX Agent",
        comments: str = "Automated stage dispatch by ContinuumX AI Orchestrator."
    ) -> Tuple[bool, str]:
        """
        Robotic dispatch: executes the exact existing dispatch function for a department.
        """
        is_ok, reason = cls.check_tool_eligibility(f"{dept}.execute_system_dispatch", rfq_id, username)
        if not is_ok:
            return False, reason

        from agents.workflow_state import WorkflowStateManager
        state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)
        customer = state["customer"]
        rfq_file = state["filepath"]

        cls._ensure_module_path("Project Management")
        from revert_workflow import send_dispatch_email, get_system_pics, get_user_email, get_user_directory

        try:
            with open(rfq_file, "r", encoding="utf-8-sig") as f:
                raw_data = json.load(f)
        except Exception as e:
            return False, f"Failed to load RFQ file for dispatch: {e}"

        # Resolve department dispatch targets
        if dept == "bom":
            from_stage = "BOM Verification"
            to_stage = "Sourcing & Cycle Time"
            stage_code = "pending_sourcing_and_cycle_time"
            raw_data["status"] = "pending_sourcing_and_cycle_time"
            raw_data["sourcing_status"] = "pending"
            raw_data["cycle_time_status"] = "pending"
            raw_data["bom_dispatched_by"] = username

        elif dept == "sourcing":
            from_stage = "Sourcing Operations"
            to_stage = "Costing"
            stage_code = "pending_costing"
            raw_data["status"] = "pending_costing"
            raw_data["sourcing_status"] = "completed"
            raw_data["sourcing_dispatched_by"] = username

        elif dept == "cycle_time":
            from_stage = "Cycle Time Operations"
            to_stage = "Costing"
            stage_code = "pending_costing"
            raw_data["cycle_time_status"] = "completed"
            raw_data["cycle_time_dispatched_by"] = username

        elif dept == "costing":
            from_stage = "Costing Analysis"
            to_stage = "NPI Gateway"
            stage_code = "pending_npi"
            raw_data["status"] = "pending_npi"
            raw_data["costing_dispatched_by"] = username

        else:
            return False, f"Unknown department for dispatch: {dept}"

        # Append history log per standard
        if "history" not in raw_data or not isinstance(raw_data["history"], list):
            raw_data["history"] = []
        now = datetime.now()
        raw_data["history"].append({
            "Date": now.strftime("%d.%m.%Y"),
            "Time": now.strftime("%H:%M:%S"),
            "Changed By": username,
            "stage": f"pending_{dept}",
            "Field Name": "Stage Dispatch",
            "Old Value": state["raw_status"],
            "New Value": raw_data.get("status", stage_code)
        })

        # Save JSON file atomically
        from utils import atomic_write_json
        atomic_write_json(rfq_file, raw_data)

        # Send official SMTP dispatch email
        try:
            user_dir = get_user_directory()
            available = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}

            # 1. Project-level PICs from RFQ JSON (Reassign Project PIC)
            project_pics = []
            if dept == "bom":
                for fld in ["sourcing_assigned_by", "cycle_time_assigned_by", "dispatched_by"]:
                    val = raw_data.get(fld)
                    if val and val not in project_pics:
                        project_pics.append(val)
            elif dept in ("sourcing", "cycle_time"):
                val = raw_data.get("costing_assigned_by") or raw_data.get("dispatched_by")
                if val and val not in project_pics:
                    project_pics.append(val)
            elif dept == "costing":
                val = raw_data.get("npi_assigned_by") or raw_data.get("dispatched_by")
                if val and val not in project_pics:
                    project_pics.append(val)

            # 2. System-level default PICs from System Users vault
            pics = get_system_pics(stage_code)
            all_to_users = list(project_pics) + [u for u in pics.get("to", []) if u not in project_pics]
            
            to_emails = []
            for u in all_to_users:
                em = available.get(u) or get_user_email(u)
                if em and "@" in em and em not in to_emails:
                    to_emails.append(em)

            cc_emails = []
            for u in pics.get("cc", []):
                em = available.get(u) or get_user_email(u)
                if em and "@" in em and em not in to_emails and em not in cc_emails:
                    cc_emails.append(em)

            sender_email = get_user_email(username) or "maic-demo@continuumx.com.my"
            if sender_email and sender_email not in to_emails and sender_email not in cc_emails:
                cc_emails.append(sender_email)

            # Fallback if no target recipients configured: send directly to dispatcher/admin
            if not to_emails:
                to_emails = [sender_email]

            send_dispatch_email(
                recipients=to_emails,
                rfq_id=rfq_id,
                customer=customer,
                from_stage=from_stage,
                to_stage=to_stage,
                comments=comments,
                dispatched_by=username,
                cc_recipients=cc_emails
            )
        except Exception as mail_err:
            logger.warning(f"Dispatch email warning: {mail_err}")

        return True, f"Successfully dispatched RFQ '{rfq_id}' from {from_stage} to {to_stage}."

    @classmethod
    def execute_batch_system_dispatch(
        cls,
        dept: str,
        rfq_ids: List[str],
        username: str = "ContinuumX Agent",
        comments: str = "Batch stage dispatch by ContinuumX AI Orchestrator."
    ) -> Tuple[List[str], List[str]]:
        """
        Batch dispatches multiple RFQs and sends a SINGLE consolidated SMTP email with a summary table.
        Returns Tuple(success_rfqs_list, failed_rfqs_with_reasons_list).
        """
        cls._ensure_module_path("Project Management")
        cls._ensure_module_path("BOM")
        from revert_workflow import (
            send_dispatch_email, get_system_pics, get_user_email, get_user_directory
        )
        from agents.workflow_state import WorkflowStateManager, WorkflowStatus
        from utils import BOM_DATA_DIR, atomic_write_json
        from datetime import datetime

        now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        success_list = []
        fail_list = []
        bulk_rfqs_payload = []
        all_to_emails = set()
        all_cc_emails = set()
        last_from_stage = "BOM Verification"
        last_to_stage = "Sourcing & Cycle Time"

        user_dir = get_user_directory()
        available = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
        sender_email = get_user_email(username) or "maic-demo@continuumx.com.my"

        for rfq_id in rfq_ids:
            eligible, reason = cls.check_tool_eligibility(f"{dept}.execute_system_dispatch", rfq_id, username)
            if not eligible:
                fail_list.append(f"{rfq_id} ({reason})")
                continue

            state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)
            rfq_file = state.get("filepath")
            if not rfq_file or not os.path.exists(rfq_file):
                fail_list.append(f"{rfq_id} (File not found)")
                continue

            try:
                with open(rfq_file, 'r', encoding='utf-8-sig') as f:
                    raw_data = json.load(f)

                customer = raw_data.get("Customer") or state.get("customer") or "Unknown"

                if dept == "bom":
                    raw_data["status"] = "pending_sourcing_and_cycle_time"
                    raw_data["sourcing_status"] = "pending"
                    raw_data["cycle_time_status"] = "pending"
                    raw_data["bom_dispatched_by"] = username
                    raw_data["bom_dispatched_at"] = now_str
                    last_from_stage = "BOM Verification"
                    last_to_stage = "Sourcing & Cycle Time"
                    stage_code = "pending_sourcing_and_cycle_time"
                elif dept == "sourcing":
                    raw_data["sourcing_status"] = "completed"
                    raw_data["sourcing_dispatched_by"] = username
                    raw_data["sourcing_dispatched_at"] = now_str
                    last_from_stage = "Sourcing"
                    stage_code = "pending_costing"
                    if raw_data.get("cycle_time_status") in ("completed", "approved"):
                        raw_data["status"] = "pending_costing"
                        last_to_stage = "Costing"
                    else:
                        last_to_stage = "Pending Cycle Time"
                elif dept == "cycle_time":
                    raw_data["cycle_time_status"] = "completed"
                    raw_data["cycle_time_dispatched_by"] = username
                    raw_data["cycle_time_dispatched_at"] = now_str
                    last_from_stage = "Cycle Time"
                    stage_code = "pending_costing"
                    if raw_data.get("sourcing_status") in ("completed", "approved"):
                        raw_data["status"] = "pending_costing"
                        last_to_stage = "Costing"
                    else:
                        last_to_stage = "Pending Sourcing"
                else:
                    raw_data["status"] = f"pending_{dept}"
                    stage_code = f"pending_{dept}"

                history = raw_data.setdefault("history", [])
                history.append({
                    "stage": raw_data["status"],
                    "Action": f"Batch Dispatched to {last_to_stage}",
                    "Changed By": username,
                    "Timestamp": now_str,
                    "comments": comments
                })

                orch = raw_data.get("orchestration", {})
                if orch:
                    orch["workflow_status"] = WorkflowStatus.IN_PROGRESS
                    if "approval" in orch:
                        orch["approval"]["required"] = False
                        orch["approval"]["approved_by"] = username
                        orch["approval"]["approved_at"] = now_str
                    raw_data["orchestration"] = orch

                atomic_write_json(rfq_file, raw_data)
                success_list.append(rfq_id)

                moqs = raw_data.get("Global MOQs")
                if not moqs:
                    for assy in raw_data.get("Assemblies", []):
                        if assy.get("Assigned MOQs"):
                            moqs = assy.get("Assigned MOQs")
                            break
                moq_disp = ", ".join(str(m) for m in moqs) if isinstance(moqs, list) else str(moqs or "Standard")
                commodity = raw_data.get("Commodity") or "Wire Harness"

                bulk_rfqs_payload.append({
                    "rfq_id": rfq_id,
                    "customer": customer,
                    "assemblies": f"{commodity} (MOQs: {moq_disp})",
                    "moqs": moqs
                })

                pics = get_system_pics(stage_code)
                for u in pics.get("to", []):
                    em = available.get(u) or get_user_email(u)
                    if em and "@" in em:
                        all_to_emails.add(em)
                for u in pics.get("cc", []):
                    em = available.get(u) or get_user_email(u)
                    if em and "@" in em:
                        all_cc_emails.add(em)

            except Exception as e:
                fail_list.append(f"{rfq_id} ({e})")

        # Send ONE single consolidated email for all batch RFQs
        if bulk_rfqs_payload:
            try:
                to_emails_list = list(all_to_emails)
                if not to_emails_list:
                    to_emails_list = [sender_email]
                cc_emails_list = [e for e in all_cc_emails if e not in to_emails_list]
                if sender_email not in cc_emails_list and sender_email not in to_emails_list:
                    cc_emails_list.append(sender_email)

                send_dispatch_email(
                    recipients=to_emails_list,
                    rfq_id=bulk_rfqs_payload[0]["rfq_id"],
                    customer=bulk_rfqs_payload[0]["customer"],
                    from_stage=last_from_stage,
                    to_stage=last_to_stage,
                    comments=comments,
                    dispatched_by=username,
                    cc_recipients=cc_emails_list,
                    bulk_rfqs=bulk_rfqs_payload
                )
            except Exception as mail_err:
                logger.warning(f"Batch dispatch email warning: {mail_err}")

        return success_list, fail_list

    @classmethod
    def revert_project(
        cls,
        rfq_id: str,
        customer: str,
        target_stage: str,
        reason: str,
        requested_by: str = "ContinuumX AI Agent",
        from_stage: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Calls the official request_revert function in Project Management."""
        cls._ensure_module_path("Project Management")
        from revert_workflow import request_revert, send_revert_email, get_user_email, get_system_pics, get_user_directory
        from agents.workflow_state import WorkflowStateManager

        if not from_stage:
            state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)
            from_stage = state.get("raw_status") or "pending_bom"

        success, msg = request_revert(rfq_id, customer, target_stage, reason, requested_by)
        if not success:
            return False, msg

        try:
            user_dir = get_user_directory()
            available = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
            target_pics = get_system_pics(target_stage)
            to_names = target_pics.get("to", [])
            to_emails = [available.get(n, get_user_email(n)) for n in to_names if (available.get(n) or get_user_email(n))]
            sender_email = get_user_email(requested_by) or "maic-demo@continuumx.com.my"
            if not to_emails:
                to_emails = [sender_email]
            cc_emails = [sender_email] if sender_email not in to_emails else []

            send_revert_email(
                recipients=to_emails,
                rfq_id=rfq_id,
                customer=customer,
                from_stage=from_stage,
                to_stage=target_stage,
                reason=reason,
                requested_by=requested_by,
                cc_recipients=cc_emails
            )
        except Exception as e:
            logger.warning(f"Revert email warning: {e}")

        return True, f"RFQ '{rfq_id}' successfully reverted to '{target_stage}'. Reason: {reason}"
