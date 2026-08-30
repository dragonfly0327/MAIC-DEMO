# ContinuumX Comprehensive Agent Tool Registry & Codebase Audit Report

## 1. Executive Summary

This document provides the exhaustive, ground-truth audit of the entire **ContinuumX Ecosystem**:
- `ref/BOM/` — BOM Creation, Header Mapping, MOQ & Target Price Assignment
- `ref/Sourcing/` — Sourcing Calculation Engine, Supplier Quote Matching, MOQ Optimization
- `ref/Cycle Time/` — Cycle Time Estimation, Process Code Maintenance, NRE Tooling
- `ref/Costing/` — Costing Calculation Engine, Summary Quotation, Executive Approval
- `ref/NPI/` — NPI Project Turn-On, Component RPN Risk Classification, Purchasing Summary
- `ref/WI/` — Work Instruction Engineering, Layout Generation, Macro Excel Compilation
- `ref/Project Management/` — Central Status Tracking, Session Lock Engine, Revert Engine

### Core Architectural Principle
The **ContinuumX Agent** does **NOT** replace, duplicate, or bypass the business logic of existing microservices. Instead, it operates as an **Autonomous Orchestration & Tool-Calling Layer** directly executing the existing functions:

```
                      ┌────────────────────────────────────────┐
                      │          USER / CHATBOT BRAIN          │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │       CONTINUUMX ORCHESTRATOR          │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          AGENT TOOL REGISTRY           │
                      │       (agents/tool_registry.py)        │
                      └───────────────────┬────────────────────┘
                                          │
       ┌──────────────┬──────────────┬────┴─────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼              ▼
 ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
 │ ref/BOM/  │  │ref/Sourcing│ │ref/CycleT.│  │ref/Costing│  │ ref/NPI/  │  │ ref/WI/   │
 └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘
```

---

## 2. Exhaustive System Action Inventory (By Module)

### A. BOM System (`ref/BOM/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `bom.import` | Import Customer BOM | `main.py` -> `verify_bom_button` | `verify_bom_workflow()` | `DataLoader.load_and_consolidate()` in `bomprocessor.py` | Excel file path(s) | Consolidated `pd.DataFrame` | Creates session in `BOM/AppData/Temp/` | None | No |
| `bom.mapping` | Column & Special Mapping | `bomformatter.py` -> `CombinedMappingPanel` | `_on_combined_confirm` | `CombinedMappingPanel._on_combined_confirm` | Header mappings, Customer, RFQ # | `(result_mapping, special_results)` | Learns to `knowledge_base/learned_column_mappings.json` | None | Yes |
| `bom.verify` | BOM Verification & MPN Check | `bomformatter.py` -> `BOMVerificationPanel` | `_on_confirm` | `BOMVerificationPanel._on_confirm` | Part review, Alt MPN matches | Verified BOM rows | Staged in memory | None | Yes |
| `bom.assign_moq` | MOQ Assignment (Global/Custom) | `bomformatter.py` -> `AssemblyMOQPanel` | `_on_confirm` | `AssemblyMOQPanel._on_confirm` | Global/Custom MOQ lists | `(assigned_moqs, global_moqs)` | Sets `"Global MOQs"`, `"Assigned MOQs"`, `"MOQ Type"` | None | Yes (Gate 1) |
| `bom.target_price` | Target Price & EAU Input | `main.py` -> `input_target_price_button` | `input_target_price_workflow()` | `TargetPriceEAUPanel._on_confirm` | Target Price dict, EAU dict | Updated `raw_data` | Sets `"Target Prices"`, `"EAU"` in JSON | None | Yes |
| `bom.save_db` | Save Verified BOM Database | `bomformatter.py` | Automatic post-confirmation | `atomic_write_json()` | Verified BOM data dictionary | Writes `{RFQ}.json` | File saved in `BOM Data/{Customer}/{RFQ}.json` | None | No |
| `bom.alt_mpn_maint` | Customer Alt MPN Maintenance | `main.py` -> `alt_mpn_maint_button` | `open_alt_mpn_maint()` | `AlternativeMPNMaintenanceDialog` in `dialogs.py` | Customer, MPN aliases | Updated dictionary | Writes `alt_mpns.json` in AppData | None | Yes |
| `bom.uom_maint` | UOM Conversion Maintenance | `main.py` -> `uom_maint_button` | `open_uom_conversion_maint()` | `UOMConversionDialog` in `dialogs.py` | Source UOM, Target UOM, Multiplier | Conversion rules | Writes `uom_conversions.json` in AppData | None | Yes |
| `bom.dispatch` | Dispatch BOM RFQ | `main.py` -> `dispatch_rfq_button` | `dispatch_rfq_workflow()` | `send_dispatch_email()` & `atomic_write_json()` | `rfq_num`, `customer`, `username` | Dispatches RFQ to Sourcing & CT | `"status": "pending_sourcing_and_cycle_time"`, `"sourcing_status": "pending"`, `"cycle_time_status": "pending"` | SMTP email to Sourcing & CT PICs, CC to sender | Yes (`EmailComposerDialog`) |

---

### B. Sourcing System (`ref/Sourcing/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `sourcing.start` | Start Sourcing Selection | `main.py` -> `start_sourcing_button` | `convert_rfq_to_bom()` | `BOMDatabaseSearchPanel.wait_for_close()` | Verified BOM selection | `search_result` tuple | Loads BOM data | None | No |
| `sourcing.calc_mode` | Calculation Mode Selection | `bomformatter.py` | `CalculationModeDialog(wizard_window)` | `CalculationModeDialog.on_confirm` | Mode: `total_usage` / `individual` | `calc_mode` string | Staged for calculation engine | None | Yes |
| `sourcing.historical` | Historical Assembly Lookup | `bomformatter.py` | `SourcedAssemblySelectionDialog` | `get_quoted_assembly_records()` | Assembly # | Quoted history matches | Selects fresh vs historical quote | None | Conditional |
| `sourcing.run_engine` | Run Sourcing Engine | `bomformatter.py` | Automatic | `SourcingEngine.process_all()` in `sourcing_engine.py` | `data_dictionary`, `assembly_moqs`, `calc_mode` | `gui_model` (winning MPNs, suppliers, prices) | Computed in memory | None | No |
| `sourcing.review_ui` | Sourcing Review & Edit UI | `sourcing_ui.py` -> `SourcingUI` | `setup_ui()` | `SourcingUI.setup_ui()` | `gui_model`, `unique_assemblies` | Interactive cards, winning MPN/MFR pairs | In-memory edits | None | No |
| `sourcing.save_progress` | Save Sourcing Progress | `sourcing_ui.py` -> `btn_save_progress` | `save_progress()` | `on_approve(is_final=False)` in `bomformatter.py` | `gui_model` | Draft JSON saved | Writes saved sourcing draft to disk | None | No |
| `sourcing.approve` | Approve Calculations | `sourcing_ui.py` -> `btn_approve` | `approve()` | `on_approve(is_final=True)` in `bomformatter.py` | `gui_model` | Sourcing saved | `"sourcing_status": "completed"` in JSON | None | Yes (Gate 2) |
| `sourcing.export_excel` | Export Sourcing Workbook | `sourcing_ui.py` -> `btn_export_excel` | `export_excel()` | `export_sourcing_to_excel()` in `bomprocessor.py` | `gui_model`, RFQ ID | Generates `.xlsx` | Saves to user path | None | No |
| `sourcing.export_missing` | Export Missing Quotes Report | `sourcing_ui.py` -> `btn_export_missing` | `export_missing_sourcing_report()` | `export_missing_sourcing_to_excel()` in `bomprocessor.py` | `gui_model`, unquoted parts | Generates Missing Quotes `.xlsx` | Saves to user path | None | No |
| `sourcing.toggle_consign` | Toggle Consignment Flag | `sourcing_ui.py` -> `btn_toggle_consign` | `toggle_consign_item()` | `SourcingUI.toggle_consign_item()` | Selected line items | Marks as Consign (Price = $0) | Updates `gui_model` | None | No |
| `sourcing.edit_pairs` | Edit MPN / MFR Pairs | `sourcing_ui.py` -> `btn_edit_pairs` | `open_pair_editor()` | `MPNMFRMatchPairEditorDialog` | Selected part | Modified pairs | Updates `gui_model` | None | Yes |
| `sourcing.sourcing_maint` | Sourcing Data Management | `main.py` -> `sourcing_maint_button` | `open_sourcing_maint()` | `SourcingMasterDataWindow` in `sourcing_master_ui.py` | Supplier quote files / manual inputs | Quote records | Writes to `Master Sourcing Data/` | None | Yes |
| `sourcing.currency_config` | Currency & Markup Config | `main.py` -> `manage_currency_config_button` | `_manage_currency_config()` | `CurrencyMarkupConfigDialog` in `dialogs.py` | Exchange rates, Markup % | Currency dictionary | Writes `currency_config.json` | None | Yes |
| `sourcing.dispatch` | Dispatch Sourcing to Costing | `main.py` -> `dispatch_sourcing_button` | `dispatch_sourcing_workflow()` | `send_dispatch_email()` & status update | `rfq_num`, `selected_assemblies` | Dispatches to Costing | `"status": "pending_costing"`, `"sourcing_dispatched_by": username` | SMTP email to Costing PIC | Yes (`EmailComposerDialog`) |

---

### C. Cycle Time System (`ref/Cycle Time/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `cycle_time.start` | Start Assign Cycle Time | `main.py` -> `start_btn` | `open_bom_selection_dialog()` | `BOMSelectionDialog.show()` | Pending BOM list | Selected `(rfq_id, customer)` | Opens editor window | None | No |
| `cycle_time.maintenance_ui` | Cycle Time Maintenance Table | `cycle_time_page.py` -> `CycleTimeMaintenanceWindow` | `setup_ui()` | `CycleTimeMaintenanceWindow.setup_ui()` | `Assembly #`, process rates | Process code grid | Staged in memory | None | No |
| `cycle_time.ai_vision` | Drawing Spec AI Extraction | Engineering Email / Drawing Archive | Vision / OCR | `analyze_drawing()` in `agents/orchestrator/cycle_time_ai.py` | Drawing PDF / Image | AWG, Length, CKTs, Terminals | Pre-fills Process table | None | No |
| `cycle_time.calculate` | Calculate Total Points & Rate | `cycle_time_page.py` -> `btn_calculate` | `calculate_totals()` | `CycleTimeModel.calculate_assembly_totals()` | Process rows, complexity multipliers | Total seconds, hourly rates | Updates summary | None | No |
| `cycle_time.save` | Save Cycle Times | `cycle_time_page.py` -> `btn_save` | `save_cycle_times()` | `CycleTimeModel.save_assembly_cycle_time()` | Process entries, seconds, points | Saved JSON | `"cycle_time_status": "completed"` in JSON | None | Yes (Gate 3) |
| `cycle_time.copy_assy` | Copy from Another Assembly | `cycle_time_page.py` -> `btn_copy_from_assy` | `copy_from_assembly()` | `CycleTimeModel.copy_assembly_rates()` | Source Assembly # | Cloned process list | Pre-fills current assembly | None | No |
| `cycle_time.manage_nre` | Assign NRE Charges (Tooling) | `cycle_time_page.py` -> `btn_nre_manage` | `open_nre_dialog()` | `NREMaintenanceDialog` in `cycle_time_page.py` | Fixture/Tooling charges, Currency | NRE summary | Saved in JSON under `"NRE"` | None | Yes |
| `cycle_time.export_excel` | Export Cycle Time Sheet | `cycle_time_page.py` -> `btn_export_excel` | `export_to_excel()` | `export_cycle_time_to_excel()` in `utils.py` | Assembly process matrix | Generates `.xlsx` | Saves to user path | None | No |
| `cycle_time.master_maint` | Cycle Time & NRE Master Maint | `main.py` -> `maint_btn` | `open_master_maint()` | `CycleTimeMasterMaintenanceDialog` | Standard process rates (Cut, Strip, Crimp, Heatshrink) | Process rate dictionary | Writes `cycle_time_rates.json` | None | Yes |
| `cycle_time.dispatch` | Dispatch Cycle Time to Costing | `main.py` -> `dispatch_btn` | `open_dispatch_dialog()` | `send_dispatch_email()` & status update | `rfq_id`, `customer`, `username` | Dispatches to Costing | `"cycle_time_status": "completed"`, advances stage | SMTP email to Costing PIC | Yes (`EmailComposerDialog`) |

---

### D. Costing System (`ref/Costing/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `costing.search` | Costing Analysis Search | `main.py` -> `btn_costing_analysis` | `_show_costing_analysis()` | `CostingAnalysisWindow.setup_ui()` | Sourcing + CT database | Table of RFQs | Opens search view | None | No |
| `costing.open_quotation` | Open Full Quotation Page | `main.py` -> `btn_open_full_quotation` | `_open_full_quotation()` | `DetailedCostingPage` in `detailed_costing_page.py` | Selected RFQ | `DetailedCostingPage` | Loads Sourcing & CT data | None | No |
| `costing.recalculate` | Detailed Costing Recalculate | `detailed_costing_page.py` | `recalculate_all()` | `CostingModel.calculate_unit_price()` | Labor rates, SG&A, Attrition, Profit | Full MOQ quotation matrix | Computes BOM cost, excess, unit prices | None | No |
| `costing.apply_margin` | Apply Target Gross Margin % | `detailed_costing_page.py` -> `btn_apply_margin` | `apply_target_margin()` | `CostingModel.solve_for_margin()` | Target Margin % (e.g. 25%) | Solved Unit Prices | Updates quotation grid | None | No |
| `costing.save_finish` | Save & Finish RFQ | `detailed_costing_page.py` -> `btn_save_finish` | `save_and_finish_rfq()` | `CostingModel.save_quotation_data()` | Final calculated quotation | Saved Quotation JSON | Writes to `Saved Quotations/{Cust}/{RFQ}.json` | None | Yes (Gate 4) |
| `costing.summary_approval` | Summary for Approval Page | `main.py` -> `btn_summary_approval` | `_show_summary_approval()` | `SummaryTablePage` in `summary_table_page.py` | Quotation JSON | Summary metrics & table | Displays Gross Margin % | None | No |
| `costing.send_email` | Send Email for Approval | `summary_table_page.py` -> `btn_send_email` | `_on_send_approval_email()` | `send_approval_email()` & `EmailComposerDialog` | Approver: Jason, Comments | Sends Executive Email | Logs to approval email history | SMTP email to Executive Manager | Yes (Gate 5) |
| `costing.export_calc_details` | Export Calculation Details Excel | `detailed_costing_page.py` -> `btn_export_calc_details` | `export_calc_details()` | `excel_exporter_details.py` | Full calculation model | Generates multi-tab `.xlsx` | Saves to user path | None | No |
| `costing.export_summary_excel` | Export Quotation Summary Excel | `summary_table_page.py` -> `btn_export_summary_excel` | `export_summary_excel()` | `excel_exporter.py` | Executive summary metrics | Generates Summary `.xlsx` | Saves to user path | None | No |
| `costing.export_summary_pdf` | Export Executive Summary PDF | `summary_table_page.py` -> `btn_export_summary_pdf` | `export_summary_pdf()` | `pdf_summary_exporter.py` | Quotation summary model | Generates Customer Quotation PDF | Saves to user path | None | No |
| `costing.commodity_config` | Commodity Configuration | `main.py` -> `btn_commodity_config` | `_open_commodity_config()` | `CommodityConfigDialog` in `dialogs.py` | Commodity factors (PCBA, Wire Harness, Fiber) | Commodity defaults | Writes `commodity_defaults.json` | None | Yes |
| `costing.quotation_remarks` | Quotation Remarks Editor | `main.py` -> `btn_quotation_remarks` | `_open_quotation_remarks()` | `QuotationRemarksDialog` in `dialogs.py` | Commodity-specific T&Cs | Remarks dictionary | Writes `quotation_remarks.json` | None | Yes |
| `costing.dispatch` | Dispatch RFQ to NPI | `main.py` -> `btn_dispatch_rfq` | `_open_dispatch_rfq()` | `send_dispatch_email()` & status update | `rfq_id`, `customer`, `username` | Dispatches to NPI | `"status": "pending_npi"`, `"costing_dispatched_by": username` | SMTP email to NPI team | Yes (`EmailComposerDialog`) |

---

### E. NPI System (`ref/NPI/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `npi.dashboard` | NPI Project Dashboard | `main.py` -> `project_dashboard` | `get_dashboard_frame()` | `NPIProjectDashboardFrame.setup_ui()` | Active batches | Project table | Read-only overview | None | No |
| `npi.award_project` | Award New Project Batch | `project_turnon_ui.py` -> `btn_award` | `on_award_project()` | `save_npi_projects()` | Dispatched RFQ, PO Number | New Project Batch Record | Writes to `npi_projects.json` | None | Yes |
| `npi.rpn_evaluate` | RPN Risk Score Evaluation | `npi_rpn_engine.py` | `NPIRPNEngine.evaluate_batch()` | `NPIRPNEngine.evaluate_batch()` | Batch components | RPN risk score (1-100) | Classified risk status | None | No |
| `npi.ml_classify` | ML Category Classification | `npi_ml_classifier.py` | `NPIMLClassifier.classify_category()` | `NPIMLClassifier.predict()` | MPN, Description | Commodity Category (ACCS, RESI, etc.) | Pre-fills RPN attributes | None | No |
| `npi.micro_dashboard` | Micro Management Grid | `main.py` -> `micro_dashboard` | `get_micro_frame()` | `NPIMicroDashboardFrame.setup_ui()` | Batch component drilldown | Risk matrix table | Interactive review | None | No |
| `npi.verification_grid` | MPN Final Verification Grid | `main.py` -> `verification` | `get_verification_frame()` | `VerificationGridFrame.setup_ui()` | Components, Approved MPNs | Verification matrix | Line item sign-off | None | Yes |
| `npi.purchasing_summary` | Consolidated Purchasing Summary | `main.py` -> `purchasing` | `get_purchasing_frame()` | `PurchasingSummaryFrame.setup_ui()` | Sourced BOMs, MOQs | Consolidated PO requisition | Purchase plan table | None | No |
| `npi.export_rpn_excel` | Export RPN Classification Excel | `project_turnon_ui.py` -> `btn_export_rpn` | `export_rpn_excel()` | `export_rpn_to_excel()` in `utils.py` | Batch RPN matrix | Generates `.xlsx` | Saves to user path | None | No |
| `npi.dispatch_to_wi` | Handover Project to WI | `project_turnon_ui.py` -> `btn_handover` | `handover_to_wi()` | Status update & email | Batch ID, Customer | Sets status to pending WI | `"status": "pending_wi"` | SMTP email to WI PIC | Yes |

---

### F. Work Instruction System (`ref/WI/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `wi.create_new` | Create New Work Instruction | `router.py` -> `btn_a` | `_open_new_wi_flow()` | `WorkInstructionEditor` in `editor.py` | Customer, RFQ, Assy # | WI Editor canvas | Initializes draft | None | No |
| `wi.open_draft` | Open Draft Selector | `router.py` -> `btn_b` | `_open_draft_selector()` | `DraftSelectorDialog` in `dialogs.py` | Status filter | Selected draft | Loads draft JSON | None | No |
| `wi.save_draft` | Save Draft WI | `editor.py` -> `btn_save` | `save_draft()` | `DataStore.save_draft_wi()` | Draft layout data | Writes `DRAFT WI/{id}.json` | `"status": "Draft"` | None | Yes |
| `wi.place_image` | Place Image on Layout | `editor.py` -> `btn_add_image` | `place_image()` | `WorkInstructionEditor.place_image()` | Photo / drawing | Placed canvas element | Staged in draft | None | No |
| `wi.crop_image` | Crop & Annotate Image | `editor.py` -> `btn_crop_image` | `crop_image()` | `ImageCropperDialog` in `dialogs.py` | Image rect coordinates | Cropped image asset | Saved to `WI PHOTO/` | None | No |
| `wi.insert_table` | Insert Process Table | `editor.py` -> `btn_add_table` | `insert_table()` | `WorkInstructionEditor.insert_table()` | Process step rows | Placed table element | Staged in draft | None | No |
| `wi.submit_review` | Submit WI for Review | `editor.py` -> `btn_submit_review` | `submit_for_review()` | `DataStore.update_wi_status()` | Draft ID | Status to Pending Review | `"status": "Pending Review"` | Email to Reviewer | Yes |
| `wi.approve_wi` | Approve Work Instruction | `editor.py` -> `btn_approve` | `approve_wi()` | `DataStore.update_wi_status()` | Draft ID, Signature | Status to Approved | `"status": "Approved"` | Email to Approver | Yes |
| `wi.export_macro_excel` | Generate Excel (.xlsm) WI | `editor.py` -> `btn_export` | `export_to_excel()` | `MacroRunner.generate_wi_excel()` in `macro.py` | Draft JSON | Generates official `.xlsm` | Saves to `WI_Log/` | None | Yes |
| `wi.process_maint` | Process Code Maintenance | `router.py` -> `btn_proc` | `_open_process_maintenance()` | `ProcessMaintenanceDialog` in `dialogs.py` | Process code definitions | Process code dictionary | Writes `wi_data_config.json` | None | Yes |
| `wi.signature_maint` | User Signature Maintenance | `router.py` -> `btn_sig` | `_open_signature_maintenance()` | `SignatureMaintenanceDialog` in `dialogs.py` | User PNG signature | Signature image file | Saved to `Master Data/Signatures/` | None | Yes |
| `wi.workflow_config` | WI Workflow Configuration | `router.py` -> `btn_wf` | `_open_workflow_configuration()` | `WorkflowConfigDialog` in `dialogs.py` | Reviewer/Approver hierarchy | Configuration dict | Writes `config.ini` | None | Yes |

---

### G. Project Management & Revert Engine (`ref/Project Management/`)

| Action ID | Action Name | UI Location | Trigger Callback | Underlying Function | Inputs | Output | State / File Changed | Notification | Approval Gate |
|---|---|---|---|---|---|---|---|---|---|
| `project.view_tree` | Project Status Overview (14 Cols) | `main.py` -> Treeview | `filter_tree()` | `BaseProjectManagementPanel.filter_tree()` | Filter text, stage filter | 14-column project grid | Read-only | None | No |
| `project.revert` | Revert RFQ to Previous Stage | Context Menu -> Revert | `on_revert_clicked()` | `request_revert()` in `revert_workflow.py` | `rfq_id`, `customer`, `target_stage`, `reason`, `user` | `(success, msg)` | Sets `"revert_pending"`, resets downstream flags, resurrects Temp session | SMTP email to upstream PICs | Yes (`RevertDialog`) |
| `project.audit_history` | View Audit Trail & History | Context Menu -> History | `view_history_dialog()` | `HistoryViewerDialog` in `dialogs.py` | RFQ ID | History log timeline | Read-only modal | None | No |
| `project.send_stuck_query` | Send Stalled Stage Query Email | Context Menu -> Stuck Query | `send_stuck_query_email()` | `StuckQueryEmailDialog` in `dialogs.py` | RFQ ID, Current PIC | Sends reminder email | Logs query in history | SMTP reminder email | Yes |
| `project.export_status_excel` | Export Project Status Excel | Treeview -> Export | `export_pm_excel()` | `export_project_status_to_excel()` | Full Treeview rows | Generates `.xlsx` | Saves to user path | None | No |
| `system.system_pics_maint` | System PICs Configuration | Header -> PICs Config | `open_pic_maintenance()` | `SystemPICMaintenanceDialog` in `dialogs.py` | Stage PIC mappings | PIC mapping JSON | Writes `system_pics.json` | None | Yes |
| `system.revert_daemon` | Background Revert Reminder | Background Thread | Periodic scan (15m) | `revert_reminder_daemon.py` | Unacknowledged reverts | Revert alert dialog | Logs reminder alerts | SMTP reminder if unhandled | No |

---

## 3. Tool Tier Taxonomy & Registration Strategy

All tools are grouped into 5 distinct operational tiers in `agents/tool_registry.py`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AGENT TOOL REGISTRY TIERS                       │
├────────────────────────┬───────────────────────────────────────────────┤
│ TIER 1: READ_ONLY      │ Instant, read-only queries (Safe for 24/7 AI) │
├────────────────────────┼───────────────────────────────────────────────┤
│ TIER 2: AUTO_ACTION    │ Background RPA computation (No UI required)   │
├────────────────────────┼───────────────────────────────────────────────┤
│ TIER 3: HUMAN_APPROVAL │ Launches native UI window for human review    │
├────────────────────────┼───────────────────────────────────────────────┤
│ TIER 4: COND_DISPATCH  │ Advances RFQ stage if business rules pass     │
├────────────────────────┼───────────────────────────────────────────────┤
│ TIER 5: HIGH_RISK      │ Stage Revert & Administrative changes         │
└────────────────────────┴───────────────────────────────────────────────┘
```

---

## 4. Execution Safety Rules

1. **Session Lock Guard**:
   - Every modifying tool **MUST** respect `acquire_session_lock(rfq_id, username)`. If an RFQ is being edited in a UI window by a human, the Agent must yield.
2. **Atomic Write Standard**:
   - All JSON updates must use `atomic_write_json()` to avoid file corruption across network drives.
3. **No Direct State Bypassing**:
   - The Agent must never manually change status fields without logging to `history` or calling `request_revert()`.
