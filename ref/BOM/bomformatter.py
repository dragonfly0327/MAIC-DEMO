import os
import sys
import json
import tkinter as tk
import pandas as pd
from utils import show_info, show_error, ask_excel_file_paths, ask_save_file_path, delete_file, STANDARD_COLUMNS, MANDATORY_COLUMNS, MULTI_SOURCE_COLUMNS, SPECIAL_SELECTION_COLUMNS, Logger, excel_folder, log_folder, acquire_session_lock, release_session_lock
from dialogs import CategoryInputDialog, ValidationDialog, SourcingCancelWarningDialog
from sourcing_wizard import CombinedMappingPanel, AssemblyMOQPanel, BOMVerificationPanel
from bomprocessor import DataLoader, BOMProcessor
from utils import DATA_PATH, get_log_file

def round_up_to_2_sig_figs(val):
    import math
    if pd.isna(val) or val <= 0:
        return 0.0
    try:
        val = float(val)
        factor = 10 ** (1 - int(math.floor(math.log10(abs(val)))))
        return math.ceil(val * factor) / factor
    except:
        return val

def verify_bom_workflow(parent_window):
    root = parent_window
    username = root.user_name
    locked_rfq = None

    wizard_window = None

    def on_wizard_close():
        nonlocal wizard_window
        if wizard_window:
            try: wizard_window.destroy()
            except: pass
            wizard_window = None

    def get_or_create_wizard_window(title_text="BOM Verification Workflow"):
        nonlocal wizard_window
        if wizard_window is None or not wizard_window.winfo_exists():
            wizard_window = tk.Toplevel(root.master)
            wizard_window.title(title_text)
            wizard_window._skip_autofit = True
            wizard_window.geometry("1200x700")
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())
        else:
            wizard_window.title(title_text)
        return wizard_window

    try:
        while True:
            # Release any previous lock
            if locked_rfq:
                release_session_lock(locked_rfq, username)
                locked_rfq = None

            if wizard_window and wizard_window.winfo_exists():
                for widget in wizard_window.winfo_children():
                    widget.destroy()
                try: wizard_window.withdraw()
                except: pass

            # Check for agent payload from Launcher
            agent_payload = None
            local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
            payload_path = os.path.join(local_appdata, "ContXs", "agent_bom_payload.json")
            if os.path.exists(payload_path):
                try:
                    with open(payload_path, 'r', encoding='utf-8') as pf:
                        agent_payload = json.load(pf)
                    try: os.remove(payload_path)
                    except: pass
                except Exception as p_err:
                    print(f"[BOMAgent Payload Notice] {p_err}")

            if agent_payload and agent_payload.get("file_path") and os.path.exists(agent_payload["file_path"]):
                file_paths = [agent_payload["file_path"]]
                session_result = "NEW"
                agent_cust_name = agent_payload.get("customer_name")
                agent_commodity = agent_payload.get("commodity")
                agent_project_title = agent_payload.get("project_title")
                agent_rfq_number = agent_payload.get("rfq_number")
                agent_mapping = agent_payload.get("suggested_mapping")
                agent_assigned_moqs = agent_payload.get("assigned_moqs")
                agent_custom_moqs = agent_payload.get("custom_moqs")
            else:
                agent_cust_name = None
                agent_commodity = None
                agent_project_title = None
                agent_rfq_number = None
                agent_mapping = None
                agent_assigned_moqs = None
                agent_custom_moqs = None

                # Step 0: Session Manager Selection View (centered on root)
                from dialogs import BOMVerificationSessionDialog
                session_dlg = BOMVerificationSessionDialog(root)
                root.wait_window(session_dlg)

                session_result = session_dlg.result
                if session_result is None:
                    # User cancelled session selection -> exit
                    on_wizard_close()
                    return

            if session_result == "NEW":
                if not agent_payload:
                    # Step 1: Select Input File
                    file_paths = ask_excel_file_paths(root)
                    if not file_paths:
                        show_info("No File Selected", "No import file selected. Operation canceled.", parent=root)
                        continue  # Go back to session picker

                # Step 2: Get Headers
                try:
                    actual_excel_headers = DataLoader.get_excel_headers(file_paths[0])
                except Exception as e:
                    show_error("Error", f"Failed to read headers: {e}", parent=root)
                    continue

                # Step 3: Mapping & Customer Info UI Loop
                initial_mapping = agent_mapping
                initial_special = agent_payload.get("suggested_special") if agent_payload else None
                initial_rfq_val = agent_rfq_number if agent_rfq_number else ""
                initial_email_val = agent_project_title if agent_project_title else ""

                # --- AGENTIC AUTO-FILL INTEGRATION ---
                if not initial_mapping or not initial_special:
                    try:
                        import sys
                        _root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        if _root_dir not in sys.path:
                            sys.path.insert(0, _root_dir)
                        from agents.skills.bom_verification_agent import BOMVerificationAgent
                        agent = BOMVerificationAgent()
                        agent_res = agent.parse_customer_bom(file_paths[0])
                        if agent_res.get("success"):
                            if not initial_mapping:
                                initial_mapping = agent_res.get("suggested_mapping")
                            if not initial_special:
                                initial_special = agent_res.get("suggested_special")
                            if not agent_project_title:
                                initial_email_val = agent_res.get("suggested_project_title", "")
                    except Exception as ex:
                        print(f"[BOMAgent Integration Notice] {ex}")

                # Ensure initial_mapping is formatted correctly for CombinedMappingPanel
                if isinstance(initial_mapping, dict):
                    formatted_mapping = {}
                    for k, v in initial_mapping.items():
                        if isinstance(v, list) or k in MULTI_SOURCE_COLUMNS:
                            formatted_mapping[k] = v
                        elif k in actual_excel_headers:
                            formatted_mapping[k] = v
                        elif v in actual_excel_headers:
                            formatted_mapping[v] = k
                    if formatted_mapping:
                        initial_mapping = formatted_mapping

                while True:
                    wizard_window = get_or_create_wizard_window("BOM Verification Workflow")
                    wizard_window.deiconify()
                    wizard_window.grab_set()
                    for widget in wizard_window.winfo_children():
                        widget.destroy()
                    wizard_window.geometry("1200x700")
                    wizard_window.state('zoomed')

                    # Initial data for mapping
                    default_cust = agent_cust_name if agent_cust_name else os.path.splitext(os.path.basename(file_paths[0]))[0]
                    mapper = CombinedMappingPanel(
                        wizard_window, actual_excel_headers, SPECIAL_SELECTION_COLUMNS, default_cust,
                        STANDARD_COLUMNS, MANDATORY_COLUMNS, SPECIAL_SELECTION_COLUMNS, MULTI_SOURCE_COLUMNS,
                        initial_mapping=initial_mapping, initial_special=initial_special,
                        initial_rfq=initial_rfq_val, initial_email=initial_email_val
                    )
                    if agent_commodity:
                        comm_str = str(agent_commodity).strip()
                        norm_comm = None
                        clow = comm_str.lower()
                        if "pcb" in clow or "board" in clow: norm_comm = "PCBA"
                        elif "wire" in clow or "harness" in clow or "cable" in clow: norm_comm = "Wire Harness"
                        elif "fiber" in clow or "fibre" in clow or "optic" in clow: norm_comm = "FIBER Optic"
                        elif "box" in clow or "build" in clow: norm_comm = "BoxBuild"
                        elif "mod" in clow: norm_comm = "Module"
                        else: norm_comm = agent_commodity
                        mapper.commodity_var.set(norm_comm)
                    if initial_email_val:
                        mapper.email_subject_var.set(initial_email_val)
                    mapper.pack(fill="both", expand=True)

                    # Handle close and cancel warning for step 3
                    wizard_window.protocol("WM_DELETE_WINDOW", lambda: mapper._on_cancel())

                    mapping_result = mapper.wait_for_close()
                    if not mapping_result:
                        wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())
                        break  # Cancel mapping -> break out to session picker

                    special_results, cust_name, rfq_num, commodity, email_subject, dynamic_mapping = mapping_result

                    # Learn from user-confirmed mapping for future BOMs
                    try:
                        import sys
                        _root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        if _root_dir not in sys.path:
                            sys.path.append(_root_dir)
                        from agents.skills.bom_verification_agent import BOMVerificationAgent
                        learn_agent = BOMVerificationAgent()
                        learn_agent.learn_mapping(cust_name, actual_excel_headers, dynamic_mapping, special_results, commodity)
                    except Exception as learn_ex:
                        print(f"[BOMAgent Learning Notice] {learn_ex}")

                    # Preserve user selections if they need to return to mapping panel later
                    initial_special = special_results
                    initial_mapping = dynamic_mapping
                    initial_rfq_val = rfq_num
                    initial_email_val = email_subject

                    success, locked_by = acquire_session_lock(rfq_num, username)
                    if not success:
                        show_error("Access Blocked", f"This RFQ ({rfq_num}) is currently being edited by {locked_by}.", parent=wizard_window)
                        wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())
                        continue  # Retry mapping panel
                    locked_rfq = rfq_num

                    # Step 4: Load and Parse Sparse Data
                    all_dfs = []
                    for fp in file_paths:
                        df_raw = DataLoader.load_and_map_dataframe(fp, special_results, dynamic_mapping, STANDARD_COLUMNS, MULTI_SOURCE_COLUMNS)
                        df_parsed = BOMProcessor.parse_sparse_bom(df_raw)
                        all_dfs.append(df_parsed)

                    df_consolidated = pd.concat(all_dfs, ignore_index=True)

                    if 'Qty' in df_consolidated.columns:
                        numeric_qty = pd.to_numeric(df_consolidated['Qty'], errors='coerce')
                        df_consolidated = df_consolidated[numeric_qty.notna()].copy()
                        df_consolidated['Qty'] = numeric_qty[numeric_qty.notna()]

                    # Helper to extract known UOM set (both From UOM and To UOM targets)
                    def get_known_uoms(uom_rules):
                        known = {rk.strip().upper() for rk in uom_rules.keys()}
                        for r in uom_rules.values():
                            if isinstance(r, dict) and r.get("to_uom"):
                                known.add(str(r.get("to_uom")).strip().upper())
                        return known

                    # UOM Conversion Scanning & Processing
                    uom_ok = True
                    if 'UOM' in df_consolidated.columns and 'Qty' in df_consolidated.columns:
                        from utils import load_uom_conversions, save_uom_conversions
                        uom_config = load_uom_conversions()
                        tolerance_pct = uom_config.get("tolerance_pct", 5.0)
                        rules = uom_config.get("rules", {})

                        unique_uoms = sorted(list(df_consolidated['UOM'].dropna().astype(str).str.strip().str.upper().unique()))
                        known_uoms = get_known_uoms(rules)
                        missing_uoms = [u for u in unique_uoms if u and u not in known_uoms]

                        # Auto-register missing UOMs as 1-to-1 identity conversion rules (e.g. KG -> KG, PCS -> PCS)
                        if missing_uoms:
                            auto_added = False
                            for m_uom in missing_uoms:
                                if m_uom not in rules:
                                    rules[m_uom] = {"to_uom": m_uom, "factor": 1.0, "apply_tolerance": False}
                                    auto_added = True

                            if auto_added:
                                uom_config["rules"] = rules
                                save_uom_conversions(uom_config)
                                known_uoms = get_known_uoms(rules)
                                missing_uoms = [u for u in unique_uoms if u and u not in known_uoms]

                        if missing_uoms:
                            from sourcing_wizard import PromptMissingUOMDialog
                            dlg = PromptMissingUOMDialog(wizard_window, missing_uoms)
                            wizard_window.wait_window(dlg)

                            uom_config = load_uom_conversions()
                            tolerance_pct = uom_config.get("tolerance_pct", 5.0)
                            rules = uom_config.get("rules", {})

                            known_uoms = get_known_uoms(rules)
                            still_missing = [u for u in unique_uoms if u and u not in known_uoms]
                            if still_missing:
                                show_error("UOM Pairing Required", "You must map all UOMs before proceeding to verification.", parent=wizard_window)
                                if locked_rfq:
                                    release_session_lock(locked_rfq, username)
                                    locked_rfq = None
                                uom_ok = False

                        if uom_ok:
                            upper_rules = {k.strip().upper(): v for k, v in rules.items()}
                            df_consolidated['Qty'] = df_consolidated['Qty'].astype('float64')
                            for idx, row in df_consolidated.iterrows():
                                uom_val = str(row['UOM']).strip().upper()
                                if uom_val in upper_rules:
                                    rule = upper_rules[uom_val]
                                    to_uom = rule.get("to_uom", uom_val)
                                    factor = float(rule.get("factor", 1.0))
                                    apply_tolerance = rule.get("apply_tolerance", False)

                                    qty_val = float(row['Qty']) if pd.notna(row['Qty']) else 0.0
                                    new_qty = qty_val * factor
                                    if apply_tolerance:
                                        rule_tol_pct = float(rule.get("tolerance_pct", tolerance_pct))
                                        new_qty = new_qty * (1.0 + rule_tol_pct / 100.0)

                                    df_consolidated.at[idx, 'Qty'] = round_up_to_2_sig_figs(new_qty)
                                    df_consolidated.at[idx, 'UOM'] = to_uom

                    if not uom_ok:
                        continue  # Return to column mapping screen with choices preserved!

                    break  # Mapping & UOM check succeeded! Break inner loop to proceed.

                if not mapping_result:
                    continue  # Break to outer session picker if user cancelled mapping panel

                assembly_status = {}
                temp_file_path = None
                cust_info = (special_results, cust_name, rfq_num, email_subject, commodity)
                is_edit_session = False

            else:
                # Resuming Flow from temporary save
                cust_info_list = session_result["customer_info"]
                cust_name = cust_info_list[1]
                rfq_num = cust_info_list[2]
                email_subject = cust_info_list[3]
                commodity = cust_info_list[4] if len(cust_info_list) > 4 else ""
                cust_info = (cust_info_list[0], cust_info_list[1], cust_info_list[2], cust_info_list[3], commodity)
                dynamic_mapping = session_result["mapping"]
                assembly_status = session_result["assembly_status"]
                df_data = session_result["df_data"]
                temp_file_path = session_dlg.temp_file_path

                success, locked_by = acquire_session_lock(rfq_num, username)
                if not success:
                    show_error("Access Blocked", f"This RFQ ({rfq_num}) is currently being edited by {locked_by}.", parent=wizard_window)
                    continue
                locked_rfq = rfq_num

                df_consolidated = pd.DataFrame(df_data)
                if 'Qty' in df_consolidated.columns:
                    df_consolidated['Qty'] = pd.to_numeric(df_consolidated['Qty'], errors='coerce')

                title_str = "BOM Verification Workflow"
                if isinstance(session_result, dict) and session_result.get("is_edit_saved", False):
                    title_str = "BOM Verification Workflow (Editing Saved BOM)"
                elif isinstance(session_result, dict) and session_result.get("is_requote", False):
                    title_str = "BOM Verification Workflow (Requote)"

                wizard_window = get_or_create_wizard_window(title_str)
                wizard_window.geometry("1200x700")
                wizard_window.state('zoomed')
                wizard_window.deiconify()
                wizard_window.grab_set()
                is_edit_session = session_result.get("is_edit_saved", False) if isinstance(session_result, dict) else False

            # Step 5: Verification UI
            for widget in wizard_window.winfo_children():
                widget.destroy()

            verifier = BOMVerificationPanel(wizard_window, df_consolidated, cust_info, dynamic_mapping, assembly_status=assembly_status, temp_file_path=temp_file_path, username=username, is_edit_saved=is_edit_session)
            verifier.pack(fill="both", expand=True)

            # Handle close and cancel warning for step 5
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: verifier._on_cancel_verification())

            verified_df = verifier.wait_for_close()
            if verified_df is None:
                # User cancelled verification -> loop back to session picker
                if locked_rfq:
                    release_session_lock(locked_rfq, username)
                    locked_rfq = None
                wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())
                continue
            else:
                break

        # Step 6: Save JSONs (Asynchronously to handle network/disk latency without freezing UI)
        import threading
        
        # Set busy cursor and disable closing
        try:
            wizard_window.config(cursor="watch")
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: None)
        except:
            pass

        def save_task():
            import time
            debug_log = r"c:\Users\User\Documents\GitHub\ContinuumXAgenticPlatform\ref\BOM\debug_save.log"
            def log_dbg(msg):
                try:
                    with open(debug_log, "a", encoding="utf-8") as lf:
                        lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
                except:
                    pass
            try:
                log_dbg("save_task started")
                from utils import BOM_DATA_DIR
                import json
                
                # 6a. BOM Data
                project_root = os.path.join(BOM_DATA_DIR, cust_name.replace(" ", "_"))
                log_dbg(f"project_root resolved to: {project_root}")
                if not os.path.exists(project_root):
                    os.makedirs(project_root)
                    log_dbg("created project_root directory")
                    
                json_path = os.path.join(project_root, f"{rfq_num.replace(' ', '_')}.json")
                log_dbg(f"json_path resolved to: {json_path}")
                
                # Build hierarchical structure
                is_requote = isinstance(session_result, dict) and session_result.get("is_requote", False)
                is_edit = (session_result != "NEW") and not is_requote and os.path.exists(json_path)
                edited_assemblies = getattr(verifier, 'edited_assemblies', set())
                
                if is_edit and edited_assemblies:
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            indiv_bom_data = json.load(f)
                    except Exception as e:
                        print(f"Error loading existing JSON for delta save: {e}")
                        is_edit = False
                        
                if is_edit and edited_assemblies:
                    indiv_bom_data["Project Title"] = email_subject
                    indiv_bom_data["Customer"] = cust_name
                    indiv_bom_data["RFQ"] = rfq_num
                    indiv_bom_data["Commodity"] = commodity
                    if "status" not in indiv_bom_data:
                        indiv_bom_data["status"] = "pending_bom"
                    # Update or add edited assemblies in-place in indiv_bom_data["Assemblies"]
                    existing_assemblies = {assy["Assy #"]: assy for assy in indiv_bom_data.get("Assemblies", [])}
                    
                    for assy, group in verified_df.groupby('Assy #'):
                        assy_str = str(assy)
                        if assy_str in edited_assemblies or assy_str not in existing_assemblies:
                            model = str(group.iloc[0].get('Assy Model', ''))
                            rev = str(group.iloc[0].get('Assy Rev', ''))
                            
                            comp_list = []
                            for row_dict in group.to_dict(orient='records'):
                                p_num = str(row_dict.get('Part', '')).strip()
                                if not p_num:
                                    continue
                                
                                comp_list.append({
                                    "Part": p_num,
                                    "Description": str(row_dict.get('Description', '')),
                                    "Qty": float(row_dict.get('Qty', 0.0)) if pd.notna(row_dict.get('Qty')) else 0.0,
                                    "UOM": str(row_dict.get('UOM', '')),
                                    "MFR": str(row_dict.get('MFR', '')),
                                    "MPN": str(row_dict.get('MPN', '')),
                                    "Line Item": str(row_dict.get('Line Item', ''))
                                })
                                
                            if assy_str in existing_assemblies:
                                assy_record = existing_assemblies[assy_str]
                                assy_record["Assy Model"] = model
                                assy_record["Assy Rev"] = rev
                                assy_record["Components"] = comp_list
                            else:
                                assy_record = {
                                    "Assy #": assy_str,
                                    "Assy Model": model,
                                    "Assy Rev": rev,
                                    "Components": comp_list
                                }
                                
                            existing_assemblies[assy_str] = assy_record
                            
                    unique_verified_assemblies = [str(a) for a in verified_df['Assy #'].unique() if pd.notna(a)]
                    indiv_bom_data["Assemblies"] = []
                    for assy_str in unique_verified_assemblies:
                        if assy_str in existing_assemblies:
                            indiv_bom_data["Assemblies"].append(existing_assemblies[assy_str])
                else:
                    # Build hierarchical structure from scratch (for NEW or if file not found)
                    indiv_bom_data = {
                        "Customer": cust_name,
                        "RFQ": rfq_num,
                        "Commodity": commodity,
                        "Project Title": email_subject,
                        "status": "pending_bom",
                        "Assemblies": []
                    }
                    
                    for assy, group in verified_df.groupby('Assy #'):
                        model = str(group.iloc[0].get('Assy Model', ''))
                        rev = str(group.iloc[0].get('Assy Rev', ''))
                        
                        comp_list = []
                        for row_dict in group.to_dict(orient='records'):
                            p_num = str(row_dict.get('Part', '')).strip()
                            if not p_num:
                                continue
                            
                            comp_list.append({
                                "Part": p_num,
                                "Description": str(row_dict.get('Description', '')),
                                "Qty": float(row_dict.get('Qty', 0.0)) if pd.notna(row_dict.get('Qty')) else 0.0,
                                "UOM": str(row_dict.get('UOM', '')),
                                "MFR": str(row_dict.get('MFR', '')),
                                "MPN": str(row_dict.get('MPN', '')),
                                "Line Item": str(row_dict.get('Line Item', ''))
                            })
                        
                        indiv_bom_data["Assemblies"].append({
                            "Assy #": str(assy),
                            "Assy Model": model,
                            "Assy Rev": rev,
                            "Components": comp_list
                        })
                        
                indiv_bom_data["bom_assigned_by"] = username or "Admin"
                from datetime import datetime
                now = datetime.now()
                creation_ts = now.strftime("%d.%m.%Y (%I:%M %p)")
                if "created_at" not in indiv_bom_data or not indiv_bom_data["created_at"]:
                    indiv_bom_data["created_at"] = creation_ts
                indiv_bom_data["bom_creation_date"] = indiv_bom_data["created_at"]

                if "history" not in indiv_bom_data or not isinstance(indiv_bom_data["history"], list):
                    indiv_bom_data["history"] = []
                indiv_bom_data["history"].append({
                    "Date": now.strftime("%d.%m.%Y"),
                    "Time": now.strftime("%H:%M:%S"),
                    "Changed By": username or "Admin",
                    "stage": "pending_bom",
                    "Field Name": "BOM Verification",
                    "Old Value": "New RFQ",
                    "New Value": "Verified"
                })

                if agent_assigned_moqs:
                    indiv_bom_data["Global MOQs"] = agent_assigned_moqs

                if agent_custom_moqs or agent_assigned_moqs:
                    for assy_rec in indiv_bom_data.get("Assemblies", []):
                        assy_num = str(assy_rec.get("Assy #", "")).strip()
                        matched_custom = None
                        if agent_custom_moqs and isinstance(agent_custom_moqs, dict):
                            for k_assy, custom_list in agent_custom_moqs.items():
                                if k_assy.lower() in assy_num.lower() or assy_num.lower() in k_assy.lower():
                                    matched_custom = custom_list
                                    break
                        if matched_custom:
                            assy_rec["Assigned MOQs"] = matched_custom
                            assy_rec["MOQ Type"] = "Custom"
                        elif agent_assigned_moqs and isinstance(agent_assigned_moqs, list):
                            assy_rec["Assigned MOQs"] = agent_assigned_moqs
                            assy_rec["MOQ Type"] = "Global"

                log_dbg("writing hierarchical BOM JSON")
                from utils import atomic_write_json
                atomic_write_json(json_path, indiv_bom_data)
                log_dbg("hierarchical BOM JSON written")
         
                # Record log to centralized backlog
                try:
                    log_dbg("calling log_backlog_event")
                    from backlog_api import log_backlog_event
                    details = {
                        "customer": cust_name,
                        "rfq_number": rfq_num,
                        "file_path": json_path,
                        "source": "BOM Verification Panel"
                    }
                    log_backlog_event(
                        event_type="VERIFY_BOM",
                        app_name="BOM App",
                        user_name=username or "Unknown User",
                        details=details
                    )
                    log_dbg("log_backlog_event completed")
                except Exception as e:
                    log_dbg(f"Failed to record backlog event: {e}")
                    print(f"Failed to record backlog event: {e}")

                # 6c. Sync/Merge to Customer Parts - Alternative MPNs
                log_dbg("resolving alternative MPN path")
                from utils import get_alternative_mpn_path, merge_mpn_mfr_pairs
                
                alt_mpn_json_path = get_alternative_mpn_path(cust_name)
                log_dbg(f"alt_mpn_json_path: {alt_mpn_json_path}")
                alt_mpn_data = {"Customer": cust_name, "Parts": {}}
                
                if os.path.exists(alt_mpn_json_path):
                    try:
                        log_dbg("loading existing alternative MPNs JSON")
                        with open(alt_mpn_json_path, 'r', encoding='utf-8') as f:
                            alt_mpn_data = json.load(f)
                        log_dbg("loaded alternative MPNs JSON successfully")
                    except Exception as e:
                        log_dbg(f"error loading alternative MPNs JSON: {e}")
                        
                if "Parts" not in alt_mpn_data:
                    alt_mpn_data["Parts"] = {}
                    
                parts_dict = alt_mpn_data["Parts"]
                
                edited_parts = getattr(verifier, 'edited_parts', set())
                log_dbg(f"edited_parts count: {len(edited_parts)}")
                parts_to_sync = []
                if session_result == "NEW":
                    log_dbg("session is NEW, syncing all parts")
                    unique_parts = verified_df[['Part', 'MFR', 'MPN']].drop_duplicates()
                    for part_tuple in unique_parts.itertuples(index=False):
                        parts_to_sync.append((str(part_tuple.Part).strip(), str(part_tuple.MFR).strip(), str(part_tuple.MPN).strip()))
                else:
                    log_dbg("resumed session, syncing edited parts only")
                    if edited_parts:
                        edited_df_parts = verified_df[verified_df['Part'].astype(str).isin(edited_parts)]
                        unique_edited_parts = edited_df_parts[['Part', 'MFR', 'MPN']].drop_duplicates()
                        for part_tuple in unique_edited_parts.itertuples(index=False):
                            parts_to_sync.append((str(part_tuple.Part).strip(), str(part_tuple.MFR).strip(), str(part_tuple.MPN).strip()))
                            
                log_dbg(f"parts_to_sync count: {len(parts_to_sync)}")
                if parts_to_sync:
                    for p_num, mfr_val, mpn_val in parts_to_sync:
                        if p_num and (mpn_val or mfr_val):
                            if p_num in parts_dict:
                                existing_rec = parts_dict[p_num]
                                merged_mpn, merged_mfr = merge_mpn_mfr_pairs(
                                    existing_rec.get("MPN", ""), existing_rec.get("MFR", ""),
                                    mpn_val, mfr_val
                                )
                                parts_dict[p_num] = {
                                    "MPN": merged_mpn,
                                    "MFR": merged_mfr
                                }
                            else:
                                parts_dict[p_num] = {
                                    "MPN": mpn_val,
                                    "MFR": mfr_val
                                }
                                
                    log_dbg("writing alternative MPNs JSON file")
                    from utils import atomic_write_json
                    atomic_write_json(alt_mpn_json_path, alt_mpn_data)
                    log_dbg("alternative MPNs JSON file written")
                    
                # Delete temp file if resuming or created during session
                if hasattr(verifier, "temp_file_path") and verifier.temp_file_path and os.path.exists(verifier.temp_file_path):
                    try:
                        log_dbg(f"deleting temp file: {verifier.temp_file_path}")
                        os.remove(verifier.temp_file_path)
                        log_dbg("temp file deleted")
                    except Exception as e:
                        log_dbg(f"error deleting temp file: {e}")
                        print(f"Error deleting temp file: {e}")
 
                log_dbg("save_task finished successfully, scheduling success callback")
                wizard_window.after(0, on_save_success)
            except Exception as ex:
                log_dbg(f"save_task failed with exception: {ex}")
                wizard_window.after(0, lambda err=ex: on_save_error(err))

        def on_save_success():
            if locked_rfq:
                release_session_lock(locked_rfq, username)
            try:
                wizard_window.config(cursor="")
                wizard_window.update()
            except:
                pass

            # Write Agent Completion Handshake Payload to LocalAppData
            try:
                assy_count = 1
                try:
                    if 'Assy#' in verified_df.columns:
                        assy_count = verified_df['Assy#'].dropna().nunique()
                    elif hasattr(verifier, 'assemblies') and verifier.assemblies:
                        assy_count = len(verifier.assemblies)
                except Exception:
                    pass

                local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
                comp_path = os.path.join(local_appdata, "ContXs", "agent_bom_completion.json")
                os.makedirs(os.path.dirname(comp_path), exist_ok=True)
                with open(comp_path, 'w', encoding='utf-8') as cf:
                    json.dump({
                        "status": "COMPLETED",
                        "rfq_id": rfq_num,
                        "customer": cust_name,
                        "assembly_count": int(assy_count) if assy_count else 1,
                        "assigned_moqs": agent_assigned_moqs,
                        "custom_moqs": agent_custom_moqs
                    }, cf, indent=4)
            except Exception as comp_err:
                print(f"[BOMCompletion Handshake Error] {comp_err}")
            show_info("Success", f"BOM Verification completed.\nData saved to:\n- Folder: BOM Data\n- Folder: Customer Parts - Alternative MPNs", parent=wizard_window)
            on_wizard_close()
            verify_bom_workflow(root)

        def on_save_error(ex):
            if locked_rfq:
                release_session_lock(locked_rfq, username)
            try:
                wizard_window.config(cursor="")
                wizard_window.update()
            except:
                pass
            on_wizard_close()
            show_error("Save Error", f"Failed to save verified BOM:\n{ex}", parent=root)
            verify_bom_workflow(root)

        threading.Thread(target=save_task, daemon=True).start()

    except Exception as e:
        import traceback
        traceback.print_exc()
        show_error("Workflow Error", str(e), parent=root)

def assign_moq_workflow(parent_window):
    root = parent_window
    username = root.user_name

    try:
        # 1. Open a new wizard window.
        wizard_window = tk.Toplevel(root.master)
        wizard_window.title("Assign MOQ Workflow")
        wizard_window._skip_autofit = True
        wizard_window.geometry("1200x700")
        wizard_window.state('zoomed')
        wizard_window.configure(bg="#EBF8FF")
        
        
        # Keep main window stable and maximized in background
        wizard_window.grab_set()
        
        def on_wizard_close():
            try: wizard_window.destroy()
            except: pass

        wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())

        locked_rfq = None
        first_run = True

        while True:
            if locked_rfq:
                release_session_lock(locked_rfq, username)
                locked_rfq = None
                
            # Clear all widgets first
            for widget in wizard_window.winfo_children():
                widget.destroy()

            search_result = None

            # Check if launched by AI Agent with specific target RFQ
            if first_run:
                first_run = False
                try:
                    local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
                    cmd_path = os.path.join(local_appdata, "ContXs", "agent_assign_moq_command.json")
                    if os.path.exists(cmd_path):
                        with open(cmd_path, 'r', encoding='utf-8') as cf:
                            cmd_data = json.load(cf)
                        target_id = str(cmd_data.get("rfq_id", "")).strip().lower()
                        os.remove(cmd_path)

                        if target_id:
                            from utils import BOM_DATA_DIR
                            import pandas as pd
                            if os.path.exists(BOM_DATA_DIR):
                                for root_dir, _, files in os.walk(BOM_DATA_DIR):
                                    for f in files:
                                        if f.endswith('.json') and not f.endswith('metadata.json'):
                                            f_base = os.path.splitext(f)[0].lower()
                                            t_clean = target_id.replace('rfq', '').replace('-', '').replace('_', '')
                                            f_clean = f_base.replace('rfq', '').replace('-', '').replace('_', '')
                                            if f_base == target_id or f_clean == t_clean:
                                                fp = os.path.join(root_dir, f)
                                                with open(fp, 'r', encoding='utf-8') as jf:
                                                    rdata = json.load(jf)
                                                
                                                cname = rdata.get("Customer") or rdata.get("customer_name") or "Customer"
                                                rnum = rdata.get("RFQ") or rdata.get("rfq_id") or target_id.upper()
                                                dstr = rdata.get("bom_creation_date") or rdata.get("Date") or ""
                                                
                                                rows = []
                                                for assy in rdata.get("Assemblies", []):
                                                    assy_no = str(assy.get("Assy #", ""))
                                                    for comp in assy.get("Components", []):
                                                        rows.append({'Assy #': assy_no})
                                                df_consol = pd.DataFrame(rows) if rows else pd.DataFrame([{'Assy #': a.get('Assy #', '')} for a in rdata.get('Assemblies', [])])
                                                search_result = ("start_moq", df_consol, cname, rnum, fp, rdata, dstr)
                                                break
                                    if search_result:
                                        break
                except Exception as ex:
                    print(f"[Auto Assign MOQ] {ex}")

            # 2. If no direct RFQ was specified, load the standard BOMDatabaseSearchPanel
            if not search_result:
                from sourcing_wizard import BOMDatabaseSearchPanel
                search_panel = BOMDatabaseSearchPanel(wizard_window, title="Assign MOQ to Verified BOM", only_assigned_moqs=False)
                search_panel.pack(fill="both", expand=True)
                
                # Close protocol for search panel
                wizard_window.protocol("WM_DELETE_WINDOW", lambda: search_panel._on_cancel())

                search_result = search_panel.wait_for_close()
                if not search_result:
                    # User cancelled search panel -> back to main menu
                    on_wizard_close()
                    return

            action, df_final_consolidated, cust_name, rfq_num, filepath, raw_data, date_str = search_result

            success, locked_by = acquire_session_lock(rfq_num, username)
            if not success:
                show_error("Access Blocked", f"This RFQ ({rfq_num}) is currently being edited by {locked_by}.", parent=root)
                continue
            locked_rfq = rfq_num

            # 3. Direct the user to the AssemblyMOQPanel where they can input or select global/custom MOQs.
            for widget in wizard_window.winfo_children():
                widget.destroy()

            wizard_window._skip_autofit = False
            wizard_window.geometry("1200x700")
            wizard_window.state('zoomed')

            unique_assemblies = df_final_consolidated['Assy #'].dropna().unique()
            
            # Load pre-existing MOQs and Global MOQs from the JSON if they exist
            initial_global_moqs = raw_data.get("Global MOQs", [])
            initial_assembly_moqs = {}
            for assy in raw_data.get("Assemblies", []):
                if "Assigned MOQs" in assy:
                    initial_assembly_moqs[assy["Assy #"]] = []
                    for x in assy["Assigned MOQs"]:
                        if str(x).strip():
                            try:
                                initial_assembly_moqs[assy["Assy #"]].append(int(float(x)))
                            except ValueError:
                                pass
                                
            # Infer initial_global_moqs if not saved directly in raw_data
            if not initial_global_moqs and initial_assembly_moqs:
                for assy in raw_data.get("Assemblies", []):
                    if assy.get("MOQ Type") == "Global" and assy.get("Assy #") in initial_assembly_moqs:
                        initial_global_moqs = initial_assembly_moqs[assy["Assy #"]]
                        break
                    
            moq_dialog = AssemblyMOQPanel(wizard_window, unique_assemblies, 
                                          initial_global_moqs=initial_global_moqs, 
                                          initial_assembly_moqs=initial_assembly_moqs if initial_assembly_moqs else None,
                                          raw_data=raw_data, current_user=username,
                                          customer_name=cust_name, rfq_number=rfq_num)
            moq_dialog.pack(fill="both", expand=True)

            # Setup close handler for MOQ panel
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: moq_dialog._on_cancel_moq())

            moq_res = moq_dialog.get_assembly_moqs()
            if len(moq_res) == 3:
                assembly_moqs, global_moqs, assembly_is_custom = moq_res
            else:
                assembly_moqs, global_moqs = moq_res[:2]
                assembly_is_custom = {}
            
            if assembly_moqs == "CANCEL" or not assembly_moqs:
                continue

            if assembly_moqs == "BACK":
                continue

            # 4. Inject "Assigned MOQs", "Global MOQs", and "MOQ Type" for each assembly in the BOM JSON raw_data
            raw_data["Global MOQs"] = [int(x) for x in global_moqs] if global_moqs else []

            for assy in raw_data.get("Assemblies", []):
                assy_num = assy.get("Assy #")
                if assy_num in assembly_moqs:
                    moq_list = [int(x) for x in assembly_moqs[assy_num] if str(x).strip().isdigit()]
                    assy["Assigned MOQs"] = moq_list
                    assy["MOQ Type"] = "Custom" if assembly_is_custom.get(assy_num, False) else "Global"

            if "history" not in raw_data:
                raw_data["history"] = []
            from datetime import datetime
            now = datetime.now()
            raw_data["history"].append({
                "Date": now.strftime("%d.%m.%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "Changed By": username or "Admin",
                "stage": raw_data.get("status") or "pending_bom",
                "Field Name": "Assigned MOQs",
                "Old Value": "Previous MOQs",
                "New Value": str(global_moqs if global_moqs else "Custom MOQs")
            })
            raw_data["bom_assigned_by"] = username or "Admin"
            raw_data["Global MOQs"] = [int(x) for x in global_moqs] if global_moqs else raw_data.get("Global MOQs", [])

            # Save the BOM JSON file back to disk
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)

            # Record log to centralized backlog
            try:
                from backlog_api import log_backlog_event
                details = {
                    "customer": cust_name,
                    "rfq_number": rfq_num,
                    "file_path": filepath,
                    "source": "Assembly MOQ Panel"
                }
                log_backlog_event(
                    event_type="ASSIGN_BOM_MOQ",
                    app_name="BOM App",
                    user_name=username or "Unknown User",
                    details=details
                )
            except Exception as e:
                print(f"Failed to record backlog event: {e}")

            # 5. Append the Customer and RFQ to assigned_moqs_metadata.json
            from utils import BOM_DATA_DIR
            meta_path = os.path.join(BOM_DATA_DIR, "assigned_moqs_metadata.json")
            
            from datetime import datetime
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            completed_entry = {
                "Customer": cust_name,
                "RFQ": rfq_num,
                "Timestamp": timestamp_str,
                "AssignedBy": username or "Unknown User"
            }

            meta_data = {"completed_moqs": []}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                        if not isinstance(meta_data, dict) or "completed_moqs" not in meta_data:
                            meta_data = {"completed_moqs": []}
                except Exception as e:
                    print(f"Error reading metadata: {e}")
                    meta_data = {"completed_moqs": []}

            exists = False
            for entry in meta_data["completed_moqs"]:
                if entry.get("Customer") == cust_name and entry.get("RFQ") == rfq_num:
                    entry["Timestamp"] = timestamp_str
                    entry["AssignedBy"] = username or "Unknown User"
                    exists = True
                    break
            
            if not exists:
                meta_data["completed_moqs"].append(completed_entry)

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=4)

            show_info("Success", "MOQs assigned and saved successfully!", parent=wizard_window)
            continue

    except Exception as e:
        import traceback
        traceback.print_exc()
        show_error("Workflow Error", str(e), parent=root)
        try: wizard_window.destroy()
        except: pass
    finally:
        if locked_rfq:
            release_session_lock(locked_rfq, username)

def is_bom_content_identical(saved_model, current_components):
    """
    Compares the saved components in a JSON file with the current components.
    We compare keys based on: Part, Comp Level, MPN, MFR, BOM Qty, UOM.
    """
    current_list = []
    for item in current_components:
        part = str(item.get('Part', '')).strip().upper()
        level = str(item.get('Comp Level', '')).strip()
        mpn = str(item.get('MPN', '')).strip().upper()
        mfr = str(item.get('MFR', '')).strip().upper()
        uom = str(item.get('UOM', '')).strip().upper()
        try:
            qty = float(item.get('BOM Qty', 0.0))
        except (ValueError, TypeError):
            qty = 0.0
            
        current_list.append((part, level, mpn, mfr, qty, uom))
        
    saved_list = []
    for item in saved_model:
        part = str(item.get('Part', '')).strip().upper()
        level = str(item.get('Comp Level', '')).strip()
        
        mpn = str(item.get('MPN', '')).strip().upper() if 'MPN' in item else None
        mfr = str(item.get('MFR', '')).strip().upper() if 'MFR' in item else None
        uom = str(item.get('UOM', '')).strip().upper() if 'UOM' in item else None
        qty = float(item.get('BOM Qty', 0.0)) if 'BOM Qty' in item else None
        
        saved_list.append((part, level, mpn, mfr, qty, uom))
        
    if len(current_list) != len(saved_list):
        return False
        
    current_list.sort()
    saved_list.sort()
    
    for i in range(len(current_list)):
        c_part, c_level, c_mpn, c_mfr, c_qty, c_uom = current_list[i]
        s_part, s_level, s_mpn, s_mfr, s_qty, s_uom = saved_list[i]
        
        if c_part != s_part or c_level != s_level:
            return False
            
        if s_mpn is not None and c_mpn != s_mpn:
            return False
        if s_mfr is not None and c_mfr != s_mfr:
            return False
        if s_uom is not None and c_uom != s_uom:
            return False
        if s_qty is not None and abs(c_qty - s_qty) > 0.0001:
            return False
            
    return True

def input_target_price_workflow(parent_window):
    root = parent_window
    username = root.user_name

    try:
        # 1. Open a new wizard window.
        wizard_window = tk.Toplevel(root.master)
        wizard_window.title("Input Target Price & EAU Workflow")
        wizard_window._skip_autofit = True
        wizard_window.geometry("1200x700")
        wizard_window.state('zoomed')
        
        # Keep main window stable and maximized in background
        wizard_window.grab_set()
        
        def on_wizard_close():
            try: wizard_window.destroy()
            except: pass

        wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())

        locked_rfq = None
        while True:
            if locked_rfq:
                release_session_lock(locked_rfq, username)
                locked_rfq = None
                
            # Clear all widgets first
            for widget in wizard_window.winfo_children():
                widget.destroy()

            # 2. Load the standard BOMDatabaseSearchPanel
            from sourcing_wizard import BOMDatabaseSearchPanel
            search_panel = BOMDatabaseSearchPanel(wizard_window, title="Input Target Price & EAU for Verified BOM", only_assigned_moqs=True, is_target_price=True)
            search_panel.pack(fill="both", expand=True)
            
            # Close protocol for search panel
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: search_panel._on_cancel())

            search_result = search_panel.wait_for_close()
            if not search_result:
                # User cancelled search panel -> back to main menu
                on_wizard_close()
                return

            action, df_final_consolidated, cust_name, rfq_num, filepath, raw_data, date_str = search_result

            success, locked_by = acquire_session_lock(rfq_num, username)
            if not success:
                from utils import show_error
                show_error("Access Blocked", f"This RFQ ({rfq_num}) is currently being edited by {locked_by}.", parent=root)
                continue
            locked_rfq = rfq_num

            # 3. Direct the user to the target price editing dialog.
            # Hide the background wizard window to keep layout clean
            wizard_window.withdraw()

            from target_price_wizard import BOMTargetPriceWizardDialog
            dialog = BOMTargetPriceWizardDialog(wizard_window.master, cust_name, rfq_num, filepath, raw_data)
            dialog.wait_window()
            
            on_wizard_close()
            return

    except Exception as e:
        import traceback
        traceback.print_exc()
        from utils import show_error
        show_error("Workflow Error", str(e), parent=root)
    finally:
        if locked_rfq:
            release_session_lock(locked_rfq, username)


def dispatch_rfq_workflow(parent_window):
    root = parent_window
    username = root.user_name

    try:
        # 1. Open a new wizard window.
        wizard_window = tk.Toplevel(root.master)
        wizard_window.title("Dispatch RFQ Workflow")
        wizard_window._skip_autofit = True
        wizard_window.geometry("1200x700")
        wizard_window.state('zoomed')
        wizard_window.configure(bg="#EBF8FF")

        # Keep main window stable and maximized in background
        wizard_window.grab_set()

        def on_wizard_close():
            try: wizard_window.destroy()
            except: pass

        wizard_window.protocol("WM_DELETE_WINDOW", lambda: on_wizard_close())

        locked_rfq = None
        while True:
            if locked_rfq:
                release_session_lock(locked_rfq, username)
                locked_rfq = None

            # Clear all widgets first
            for widget in wizard_window.winfo_children():
                widget.destroy()

            # 2. Load the standard BOMDatabaseSearchPanel in dispatch mode
            from sourcing_wizard import BOMDatabaseSearchPanel
            search_panel = BOMDatabaseSearchPanel(wizard_window, title="Dispatch RFQ to Sourcing & Cycle Time", only_assigned_moqs=True, is_target_price=False, is_dispatch=True)
            search_panel.pack(fill="both", expand=True)

            # Close protocol for search panel
            wizard_window.protocol("WM_DELETE_WINDOW", lambda: search_panel._on_cancel())

            search_result = search_panel.wait_for_close()
            if not search_result:
                # User cancelled search panel -> back to main menu
                on_wizard_close()
                return

            action, df_final_consolidated, cust_name, rfq_num, filepath, raw_data, date_str = search_result

            from utils import messagebox
            if not messagebox.askyesno("Confirm Dispatch", f"Are you sure you want to dispatch RFQ '{rfq_num}' to Sourcing & Cycle Time?", parent=wizard_window):
                continue

            success, locked_by = acquire_session_lock(rfq_num, username)
            if not success:
                from utils import show_error
                show_error("Access Blocked", f"This RFQ ({rfq_num}) is currently being edited by {locked_by}.", parent=root)
                continue
            locked_rfq = rfq_num

            # Trigger Email Notification Composer
            # Ensure Project Management is in path
            import sys
            pm_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Project Management"))
            if pm_dir not in sys.path:
                sys.path.append(pm_dir)
            from revert_workflow import EmailComposerDialog, get_user_directory, get_user_email, send_dispatch_email
            
            user_dir = get_user_directory()
            available_recipients = {}
            for name, info in user_dir.items():
                if info.get("email"):
                    available_recipients[name] = info["email"].strip()
                    
            sender_email = get_user_email(username)
            
            # Resolve default To and CC PICs from system_pics.json
            from revert_workflow import get_system_pics
            pics_config = get_system_pics("pending_sourcing_and_cycle_time")
            target_to_names = pics_config.get("to", [])
            target_cc_names = pics_config.get("cc", [])
            
            target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
            target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in target_cc_names]
            
            if sender_email and sender_email not in target_cc_emails:
                target_cc_emails.append(sender_email)
                
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            
            subject = f"[ContinuumX] RFQ Dispatch Notification - RFQ {rfq_num} ({cust_name}) - BOM Verification Completed"
            
            body_template = f"""Dear {{recipient}},

The BOM Verification and target price assignation has been successfully completed and dispatched for the following RFQ:

--------------------------------------------------
RFQ Number:     {rfq_num}
Customer:       {cust_name}
From Stage:     BOM Verification
Sent To Stage:  Sourcing & Cycle Time
Dispatched By:  {username}
Dispatched At:  {now_str}
--------------------------------------------------

Comments / Message:
{{comments}}

Please review the status and proceed with Sourcing and Cycle Time assignments.
"""
            composer = EmailComposerDialog(
                wizard_window,
                sender_name=username,
                sender_email=sender_email,
                recipient_name=target_to_names,
                recipient_email=target_to_emails,
                subject=subject,
                body_template=body_template,
                default_cc=target_cc_emails,
                available_recipients=available_recipients
            )
            wizard_window.wait_window(composer)
            
            if not composer.result:
                # User cancelled email dispatch -> release lock and continue
                release_session_lock(rfq_num, username)
                locked_rfq = None
                continue
                
            res = composer.result
            to_emails = res.get("to_emails", target_to_emails)
            cc_emails = res.get("cc_emails", target_cc_emails)
            comments = res.get("comments", "")
            custom_subject = res.get("subject", subject)
            
            # Send email
            send_dispatch_email(
                recipients=to_emails if to_emails else target_to_emails,
                rfq_id=rfq_num,
                customer=cust_name,
                from_stage="BOM Verification",
                to_stage="Sourcing & Cycle Time",
                comments=comments,
                dispatched_by=username,
                cc_recipients=cc_emails,
                subject=custom_subject
            )

            # Update JSON status
            raw_data["status"] = "pending_sourcing_and_cycle_time"
            raw_data["sourcing_status"] = "pending"
            raw_data["cycle_time_status"] = "pending"
            if "revert_pending" in raw_data:
                raw_data["revert_pending"]["acknowledged"] = True

            if "history" not in raw_data:
                raw_data["history"] = []
            from datetime import datetime
            now = datetime.now()
            raw_data["history"].append({
                "Date": now.strftime("%d.%m.%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "Changed By": username or "Admin",
                "stage": "pending_bom",
                "Field Name": "Stage Dispatch",
                "Old Value": "pending_bom",
                "New Value": "pending_sourcing_and_cycle_time"
            })
            raw_data["bom_dispatched_by"] = username or "Admin"

            # Save the BOM JSON file back to disk
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)

            # Register in assigned_moqs_metadata.json
            from utils import BOM_DATA_DIR, atomic_write_json
            assigned_moqs_path = os.path.normpath(os.path.join(BOM_DATA_DIR, "assigned_moqs_metadata.json"))
            try:
                ameta = {"completed_moqs": []}
                if os.path.exists(assigned_moqs_path):
                    with open(assigned_moqs_path, 'r', encoding='utf-8') as f:
                        ameta = json.load(f)
                if not any(x.get("RFQ") == rfq_num and x.get("Customer") == cust_name for x in ameta.get("completed_moqs", [])):
                    ameta.get("completed_moqs", []).append({
                        "Customer": cust_name,
                        "RFQ": rfq_num,
                        "Timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "AssignedBy": username or "Admin"
                    })
                    atomic_write_json(assigned_moqs_path, ameta)
            except Exception as ex:
                print(f"Error updating assigned MOQs metadata on BOM dispatch: {ex}")

            # Record log to centralized backlog
            try:
                from backlog_api import log_backlog_event
                details = {
                    "customer": cust_name,
                    "rfq_number": rfq_num,
                    "file_path": filepath,
                    "source": "BOM Dispatch Panel"
                }
                log_backlog_event(
                    event_type="DISPATCH_BOM",
                    app_name="BOM App",
                    user_name=username or "Unknown User",
                    details=details
                )
            except Exception as e:
                print(f"Failed to record backlog event: {e}")

            # Write agent completion handshake for Brain to advance to Sourcing stage
            try:
                local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
                comp_dir = os.path.join(local_appdata, "ContXs")
                os.makedirs(comp_dir, exist_ok=True)
                with open(os.path.join(comp_dir, "agent_bom_dispatch_completion.json"), 'w', encoding='utf-8') as df:
                    json.dump({"rfq_id": rfq_num, "customer": cust_name, "status": "dispatched_to_sourcing"}, df, indent=2)
            except Exception as ex:
                print(f"Error writing dispatch completion: {ex}")

            from utils import show_info
            show_info("Success", f"RFQ '{rfq_num}' successfully dispatched to Sourcing & Cycle Time!", parent=wizard_window)
            
            # Close the wizard window and return to launcher
            on_wizard_close()
            try:
                root.destroy()
            except Exception:
                pass
            return

    except Exception as e:
        import traceback
        traceback.print_exc()
        from utils import show_error
        show_error("Workflow Error", str(e), parent=root)
        try: wizard_window.destroy()
        except: pass
    finally:
        if locked_rfq:
            release_session_lock(locked_rfq, username)

