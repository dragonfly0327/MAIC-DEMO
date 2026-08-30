import os
import json
import time
import configparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import tkinter as tk
from tkinter import ttk

def load_shared_config():
    """Loads configuration from Project Management config.ini (or WI fallback)."""
    config = configparser.ConfigParser()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pm_config_file = os.path.normpath(os.path.join(current_dir, "config.ini"))
    wi_config_file = os.path.normpath(os.path.join(current_dir, "..", "WI", "config.ini"))
    
    if os.path.exists(pm_config_file):
        try:
            config.read(pm_config_file, encoding='utf-8')
        except Exception as e:
            print(f"[RevertWorkflow] Error reading PM config: {e}")
    elif os.path.exists(wi_config_file):
        try:
            config.read(wi_config_file, encoding='utf-8')
        except Exception as e:
            print(f"[RevertWorkflow] Error reading WI config: {e}")
    return config

def get_paths():
    config = load_shared_config()
    
    # Path fallbacks matching the platform
    pm_server_path = config.get('PATHS', 'PM_SERVER_PATH', fallback='D:/RadysisAsia MockServer/Project Management/AppData').replace('\\', '/')
    bom_server_path = config.get('PATHS', 'BOM_SERVER_PATH', fallback='D:/RadysisAsia MockServer/BOM/AppData').replace('\\', '/')
    sourcing_server_path = config.get('PATHS', 'SOURCING_SERVER_PATH', fallback='D:/RadysisAsia MockServer/Sourcing/AppData').replace('\\', '/')
    
    bom_data_dir = os.path.normpath(os.path.join(bom_server_path, "BOM Data"))
    individual_bom_data_dir = os.path.normpath(os.path.join(sourcing_server_path, "Individual BOM Data"))
    pm_appdata_dir = os.path.normpath(pm_server_path)
    
    return bom_data_dir, individual_bom_data_dir, pm_appdata_dir

def _ensure_launcher_path():
    if getattr(sys, 'frozen', False):
        c_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        c_dir = os.path.dirname(os.path.abspath(__file__))

    paths = [
        c_dir,
        os.path.normpath(os.path.join(c_dir, "..")),
        os.path.normpath(os.path.join(c_dir, "..", "..")),
    ]
    for p in paths:
        if p and os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)
    return c_dir

def _get_central_server_path():
    """
    Returns the central server path (ContXpps) configured in config.ini [Network]->ServerPath,
    CONTXS_SERVER_PATH environment variable, or active_session.json.
    Never falls back to relative client paths like base_dir/../../.
    """
    # 1. Check environment variable set when spawned from portal
    env_sp = os.environ.get("CONTXS_SERVER_PATH", "").strip()
    if env_sp and os.path.exists(env_sp):
        return os.path.normpath(env_sp)

    # 2. Check active launcher session cache in %LOCALAPPDATA%/ContXs
    try:
        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
        session_file = os.path.join(local_appdata, "ContXs", "active_session.json")
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as sf:
                sdata = json.load(sf)
                if isinstance(sdata, dict):
                    sp = str(sdata.get("server_path", "")).strip()
                    if sp and os.path.exists(sp):
                        return os.path.normpath(sp)
    except Exception:
        pass

    # 3. Check config.ini in local executable directory
    base_dir = _ensure_launcher_path()
    cfg_path = os.path.join(base_dir, "config.ini")
    if os.path.exists(cfg_path):
        try:
            cfg = configparser.ConfigParser()
            cfg.read(cfg_path, encoding='utf-8')
            if 'Network' in cfg and 'ServerPath' in cfg['Network']:
                sp = cfg['Network']['ServerPath'].strip()
                if sp:
                    return os.path.normpath(sp)
            if 'PATHS' in cfg and 'CENTRAL_SERVER_PATH' in cfg['PATHS']:
                sp = cfg['PATHS']['CENTRAL_SERVER_PATH'].strip()
                if sp:
                    return os.path.normpath(sp)
        except Exception as e:
            print(f"[RevertWorkflow] Error reading config.ini ServerPath: {e}")

    # 4. Check parent directories for config.ini with [Network] ServerPath
    curr = base_dir
    for _ in range(3):
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        p_cfg = os.path.join(parent, "config.ini")
        if os.path.exists(p_cfg):
            try:
                cfg = configparser.ConfigParser()
                cfg.read(p_cfg, encoding='utf-8')
                if 'Network' in cfg and 'ServerPath' in cfg['Network']:
                    sp = cfg['Network']['ServerPath'].strip()
                    if sp:
                        return os.path.normpath(sp)
            except Exception:
                pass
        curr = parent

    # Fallback to env_sp or base_dir if config file unavailable
    return os.path.normpath(env_sp) if env_sp else base_dir

def get_launcher_smtp_settings():
    """
    Reads SMTP settings from launcher's central system_settings.json file via AuthManager or direct JSON reading.
    """
    server_path = _get_central_server_path()
    try:
        from auth_manager import AuthManager
        auth = AuthManager(server_path)
        settings = auth.system_settings
        
        smtp_server = settings.get("smtp_server", "smtp.gmail.com")
        smtp_port = int(settings.get("smtp_port", 465))
        sender_email = settings.get("email_user", "")
        encrypted_pass = settings.get("email_pass", "")
        sender_password = auth.decrypt_secret(encrypted_pass) if encrypted_pass else ""

        if sender_email and sender_password:
            return smtp_server, smtp_port, sender_email, sender_password
    except Exception as e:
        print(f"[RevertWorkflow] AuthManager import or load failed: {e}. Reading system_settings.json directly...")

    # Direct reading fallback for compiled EXEs without auth_manager module
    try:
        settings_file = os.path.join(server_path, "security", "system_settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as sf:
                settings = json.load(sf)
                if isinstance(settings, dict):
                    smtp_server = settings.get("smtp_server", "smtp.gmail.com")
                    smtp_port = int(settings.get("smtp_port", 465))
                    sender_email = settings.get("email_user", "")
                    encrypted_pass = settings.get("email_pass", "")
                    
                    if encrypted_pass:
                        import base64
                        internal_key = "CONTXS_PROTECT_2026"
                        raw_bytes = base64.b64decode(encrypted_pass).decode()
                        sender_password = "".join(chr(ord(c) ^ ord(internal_key[i % len(internal_key)])) for i, c in enumerate(raw_bytes))
                    else:
                        sender_password = ""

                    if sender_email and sender_password:
                        return smtp_server, smtp_port, sender_email, sender_password
    except Exception as ex:
        print(f"[RevertWorkflow] Error reading system_settings.json directly: {ex}")

    return None

def get_smtp_settings():
    launcher_smtp = get_launcher_smtp_settings()
    if launcher_smtp and launcher_smtp[2] and launcher_smtp[3]:
        return launcher_smtp
        
    config = load_shared_config()
    smtp_server = config.get('SMTP', 'smtp_server', fallback='')
    smtp_port = config.getint('SMTP', 'smtp_port', fallback=465)
    sender_email = config.get('SMTP', 'sender_email', fallback='')
    sender_password = config.get('SMTP', 'sender_password', fallback='')

    if smtp_server and sender_email and sender_password:
        return smtp_server, smtp_port, sender_email, sender_password

    return None, None, None, None

def get_smtp_connection(smtp_server, smtp_port, sender_email, sender_password):
    """Returns an authenticated SMTP connection supporting SSL (465) and STARTTLS (587/others)."""
    if not smtp_server or not sender_email or not sender_password:
        raise ConnectionError("Error: Server disconnected. Configured SMTP settings not found.")

    port = int(smtp_port) if smtp_port else 465
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(sender_email, sender_password)
        return server
    except Exception as e:
        raise ConnectionError(f"Error: Server disconnected ({e})")

def get_user_directory():
    """Loads all users from Launcher Portal's central security vault (users.json via AuthManager or direct JSON reading)."""
    current_dir = _ensure_launcher_path()
    server_path = _get_central_server_path()
    user_directory = {}
    try:
        from auth_manager import AuthManager
        auth = AuthManager(server_path)
        for u_name, u_info in auth.users.items():
            user_directory[u_name] = {
                "email": u_info.get("email", "").strip(),
                "role": u_info.get("role", "User")
            }
    except Exception as e:
        print(f"[RevertWorkflow] AuthManager load error: {e}. Reading users.json directly...")

    if not user_directory:
        users_file = os.path.join(server_path, "security", "users.json")
        if os.path.exists(users_file):
            try:
                with open(users_file, 'r', encoding='utf-8') as uf:
                    udata = json.load(uf)
                    if isinstance(udata, dict):
                        for u_name, u_info in udata.items():
                            if isinstance(u_info, dict):
                                user_directory[u_name] = {
                                    "email": u_info.get("email", "").strip(),
                                    "role": u_info.get("role", "User")
                                }
            except Exception as ex:
                print(f"[RevertWorkflow] Error reading users.json directly: {ex}")

    # Merge active launcher user session if present
    try:
        from system_login import get_launcher_user_session
        sess = get_launcher_user_session()
        if sess and sess.get("username"):
            u_name = sess["username"].strip()
            u_em = sess.get("email", "").strip()
            u_rl = sess.get("role", "User").strip()
            if u_name:
                if u_name not in user_directory:
                    user_directory[u_name] = {"email": u_em, "role": u_rl}
                elif u_em:
                    user_directory[u_name]["email"] = u_em
    except Exception:
        pass

    # Merge local user_directory.json if available
    user_dir_file = os.path.normpath(os.path.join(current_dir, "user_directory.json"))
    if os.path.exists(user_dir_file):
        try:
            with open(user_dir_file, 'r', encoding='utf-8-sig') as f:
                local_dir = json.load(f)
                if isinstance(local_dir, dict):
                    for k, v in local_dir.items():
                        if k not in user_directory:
                            user_directory[k] = v
                        elif isinstance(v, dict) and v.get("email") and not user_directory[k].get("email"):
                            user_directory[k]["email"] = v["email"]
        except Exception:
            pass

    return user_directory

def get_user_email(name):
    if not name or str(name).strip().lower() in ("unassigned", "-", "none", ""):
        return ""
    name_clean = str(name).strip()

    # 1. Check active session if name matches current logged-in user
    try:
        from system_login import get_launcher_user_session
        sess = get_launcher_user_session()
        if sess and sess.get("username", "").strip().lower() == name_clean.lower():
            if sess.get("email", "").strip():
                return sess["email"].strip()
    except Exception:
        pass

    # 2. Lookup in get_user_directory() with normalized substring matching
    users = get_user_directory()
    n_norm = name_clean.lower().replace(" ", "").replace("_", "")
    for u_name, u_info in users.items():
        u_norm = u_name.lower().replace(" ", "").replace("_", "")
        if u_norm == n_norm or (len(n_norm) >= 3 and (n_norm in u_norm or u_norm in n_norm)):
            em = u_info.get("email", "").strip() if isinstance(u_info, dict) else str(u_info).strip()
            if em and "@" in em:
                return em

    # 3. If name is already a valid email address
    if "@" in name_clean:
        return name_clean

    # 4. Generate unique domain handle for user instead of assigning system_sender fallback
    clean_handle = name_clean.lower().replace(" ", "")
    return f"{clean_handle}@continuumx.com.my"

def resolve_bom_filepath(arg1, arg2=None, bom_data_dir=None):
    if arg1 and os.path.exists(str(arg1)):
        return str(arg1)
    
    rfq_id = str(arg1).strip() if arg1 else ""
    customer = str(arg2).strip() if arg2 else ""
    
    dirs_to_search = []
    if bom_data_dir and os.path.exists(bom_data_dir):
        dirs_to_search.append(bom_data_dir)
        
    bom_data_dir_default, _, _ = get_paths()
    if os.path.exists(bom_data_dir_default) and bom_data_dir_default not in dirs_to_search:
        dirs_to_search.append(bom_data_dir_default)

    safe_c = customer.replace('/', '_').replace('\\', '_').replace(' ', '_')
    safe_r = rfq_id.replace('/', '_').replace('\\', '_').replace(' ', '_')

    for bdir in dirs_to_search:
        if safe_c and safe_r:
            candidate = os.path.join(bdir, safe_c, f"{safe_r}.json")
            if os.path.exists(candidate):
                return candidate
        for root_dir, _, files in os.walk(bdir):
            for fname in files:
                if fname.lower().endswith(".json"):
                    if safe_r and (fname.lower() == f"{safe_r}.json".lower() or fname.lower() == f"{rfq_id}.json".lower()):
                        return os.path.join(root_dir, fname)
    return None

find_bom_file = resolve_bom_filepath

def request_revert(*args, **kwargs):
    """
    Core function to revert an RFQ to an earlier stage.
    Appends to history, adds revert_pending block, and modifies the status field.
    Resets sub-statuses if reverting to or before Sourcing/Cycle Time.
    Supports both 4-positional (bom_filepath, target_stage, reason, requested_by)
    and 6-positional (rfq_id, customer, target_stage, reason, requested_by, bom_data_dir).
    """
    if len(args) >= 5 or "bom_data_dir" in kwargs or ("customer" in kwargs and "rfq_id" in kwargs):
        rfq_id = args[0] if len(args) > 0 else kwargs.get("rfq_id")
        customer = args[1] if len(args) > 1 else kwargs.get("customer")
        target_stage = args[2] if len(args) > 2 else kwargs.get("target_stage")
        reason = args[3] if len(args) > 3 else kwargs.get("reason")
        requested_by = args[4] if len(args) > 4 else kwargs.get("requested_by", "Module User")
        bom_data_dir = args[5] if len(args) > 5 else kwargs.get("bom_data_dir")
        
        bom_filepath = resolve_bom_filepath(rfq_id, customer, bom_data_dir)
    else:
        bom_filepath = args[0] if len(args) > 0 else kwargs.get("bom_filepath")
        target_stage = args[1] if len(args) > 1 else kwargs.get("target_stage")
        reason = args[2] if len(args) > 2 else kwargs.get("reason")
        requested_by = args[3] if len(args) > 3 else kwargs.get("requested_by", "Module User")
        if bom_filepath and not os.path.exists(bom_filepath):
            bom_filepath = resolve_bom_filepath(bom_filepath)

    if not bom_filepath or not os.path.exists(bom_filepath):
        return False, f"BOM file not found at: {bom_filepath or (args[0] if args else '')}"

    try:
        with open(bom_filepath, 'r', encoding='utf-8-sig') as f:
            bom_data = json.load(f)
            
        rfq_id = bom_data.get("RFQ", "")
        customer = bom_data.get("Customer", "")
        from_stage = bom_data.get("status", "pending_bom")
        
        # Prepare timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        
        # 1. Update revert pending block
        bom_data["revert_pending"] = {
            "target_stage": target_stage,
            "pre_revert_stage": from_stage,
            "reason": reason,
            "requested_by": requested_by,
            "requested_at": now_str,
            "follow_up_sent_at": None,
            "acknowledged": False
        }
        
        # 2. Append to history list
        if "revert_history" not in bom_data or not isinstance(bom_data["revert_history"], list):
            bom_data["revert_history"] = []
            
        bom_data["revert_history"].append({
            "timestamp": now_str,
            "requested_by": requested_by,
            "reason": reason,
            "from_stage": from_stage,
            "to_stage": target_stage
        })
        
        # 3. Update main status to the reverted stage
        bom_data["status"] = target_stage
        
        # 4. Clean up sub-statuses if reverting to Sourcing / BOM
        _, individual_bom_data_dir, _ = get_paths()
        
        if target_stage in ["pending_bom", "pending_sourcing_and_cycle_time"]:
            bom_data["sourcing_status"] = "pending"
            bom_data["cycle_time_status"] = "pending"
            
            # Recreate session in TEMP_DIR if reverting to BOM Verification
            if target_stage == "pending_bom":
                try:
                    config_cfg = load_shared_config()
                    bom_server_path = config_cfg.get('PATHS', 'BOM_SERVER_PATH', fallback='D:/RadysisAsia MockServer/BOM/AppData').replace('\\', '/')
                    temp_dir = os.path.normpath(os.path.join(bom_server_path, "Temp"))
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    
                    import uuid
                    session_filename = f"BOM_Session_{uuid.uuid4().hex}.json"
                    temp_filepath = os.path.join(temp_dir, session_filename)
                    
                    # Reconstruct df_data from Assemblies/Components
                    df_data = []
                    for assy in bom_data.get("Assemblies", []):
                        assy_num = assy.get("Assy #", "")
                        assy_model = assy.get("Assy Model", "")
                        assy_rev = assy.get("Assy Rev", "")
                        for comp in assy.get("Components", []):
                            df_data.append({
                                "Assy #": assy_num,
                                "Assy Model": assy_model,
                                "Assy Rev": assy_rev,
                                "Part": comp.get("Part", ""),
                                "Description": comp.get("Description", ""),
                                "Qty": comp.get("Qty", 1.0),
                                "UOM": comp.get("UOM", ""),
                                "MFR": comp.get("MFR", ""),
                                "MPN": comp.get("MPN", ""),
                                "Line Item": comp.get("Line Item", "")
                            })
                            
                    customer_info = [
                        None,
                        bom_data.get("Customer", ""),
                        bom_data.get("RFQ", ""),
                        "" # Remarks
                    ]
                    
                    session_data = {
                        "is_edit_saved": False,
                        "customer_info": customer_info,
                        "mapping": {},
                        "assembly_status": {assy.get("Assy #", ""): "Viewed" for assy in bom_data.get("Assemblies", [])},
                        "df_data": df_data,
                        "temp_file_path": temp_filepath,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    with open(temp_filepath, 'w', encoding='utf-8') as sf:
                        json.dump(session_data, sf, indent=4)
                        
                    print(f"[RevertWorkflow] Successfully recreated BOM Verification session file: {session_filename}")
                except Exception as ses_err:
                    print(f"[RevertWorkflow] Failed to recreate BOM Verification session: {ses_err}")
            
            # Remove from sourcing_metadata.json
            sourcing_meta_path = os.path.join(individual_bom_data_dir, "sourcing_metadata.json")
            if os.path.exists(sourcing_meta_path):
                try:
                    with open(sourcing_meta_path, 'r', encoding='utf-8-sig') as f:
                        smeta = json.load(f)
                    if isinstance(smeta, dict) and "completed_sourcing" in smeta:
                        smeta["completed_sourcing"] = [
                            entry for entry in smeta["completed_sourcing"]
                            if not (entry.get("Customer") == customer and entry.get("RFQ") == rfq_id)
                        ]
                        with open(sourcing_meta_path, 'w', encoding='utf-8') as f:
                            json.dump(smeta, f, indent=4)
                except Exception as ex:
                    print(f"[RevertWorkflow] Error removing sourcing metadata entry: {ex}")
                    
            # Remove from cycletime_metadata.json
            cycletime_meta_path = os.path.join(individual_bom_data_dir, "cycletime_metadata.json")
            if os.path.exists(cycletime_meta_path):
                try:
                    with open(cycletime_meta_path, 'r', encoding='utf-8-sig') as f:
                        cmeta = json.load(f)
                    if isinstance(cmeta, dict) and "completed_cycletime" in cmeta:
                        cmeta["completed_cycletime"] = [
                            entry for entry in cmeta["completed_cycletime"]
                            if not (entry.get("RFQ") == rfq_id and entry.get("Customer") == customer)
                        ]
                        with open(cycletime_meta_path, 'w', encoding='utf-8') as f:
                            json.dump(cmeta, f, indent=4)
                except Exception as ex:
                    print(f"[RevertWorkflow] Error removing cycletime metadata entry: {ex}")
                    
            # Remove from assigned_moqs_metadata.json (BOM dispatch record) so Sourcing/CycleTime won't show it
            bom_data_parent = os.path.dirname(individual_bom_data_dir)
            assigned_moqs_path = os.path.join(bom_data_parent, "assigned_moqs_metadata.json")
            if not os.path.exists(assigned_moqs_path):
                assigned_moqs_path = os.path.join(individual_bom_data_dir, "assigned_moqs_metadata.json")
            if os.path.exists(assigned_moqs_path):
                try:
                    with open(assigned_moqs_path, 'r', encoding='utf-8-sig') as f:
                        ameta = json.load(f)
                    if isinstance(ameta, dict) and "completed_moqs" in ameta:
                        ameta["completed_moqs"] = [
                            entry for entry in ameta["completed_moqs"]
                            if not (entry.get("RFQ") == rfq_id and entry.get("Customer") == customer)
                        ]
                        with open(assigned_moqs_path, 'w', encoding='utf-8') as f:
                            json.dump(ameta, f, indent=4)
                        print(f"[RevertWorkflow] Removed {rfq_id}/{customer} from assigned_moqs_metadata.json")
                except Exception as ex:
                    print(f"[RevertWorkflow] Error removing assigned_moqs metadata entry: {ex}")

                    
        # Write back BOM JSON file
        with open(bom_filepath, 'w', encoding='utf-8') as f:
            json.dump(bom_data, f, indent=4)
            
        return True, "Revert successfully executed in database."
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Database update failed: {e}"


def send_revert_email(*args, **kwargs):
    """
    Sends notification email to PICs about the revert request using rich HTML table layout.
    """
    if "to_emails" in kwargs or "sender_name" in kwargs or "body" in kwargs:
        recipients = kwargs.get("to_emails") or kwargs.get("recipients") or []
        cc_recipients = kwargs.get("cc_emails") or kwargs.get("cc_recipients") or []
        rfq_id = kwargs.get("rfq_id", "")
        customer = kwargs.get("customer", "")
        from_stage = kwargs.get("from_stage", "")
        to_stage = kwargs.get("to_stage", "")
        reason = kwargs.get("reason") or kwargs.get("body", "")
        requested_by = kwargs.get("requested_by") or kwargs.get("sender_name", "Module User")
        custom_subject = kwargs.get("subject")
    else:
        recipients = args[0] if len(args) > 0 else kwargs.get("recipients")
        rfq_id = args[1] if len(args) > 1 else kwargs.get("rfq_id", "")
        customer = args[2] if len(args) > 2 else kwargs.get("customer", "")
        from_stage = args[3] if len(args) > 3 else kwargs.get("from_stage", "")
        to_stage = args[4] if len(args) > 4 else kwargs.get("to_stage", "")
        reason = args[5] if len(args) > 5 else kwargs.get("reason", "")
        requested_by = args[6] if len(args) > 6 else kwargs.get("requested_by", "Module User")
        cc_recipients = args[7] if len(args) > 7 else kwargs.get("cc_recipients")
        custom_subject = kwargs.get("subject")

    if isinstance(reason, dict):
        custom_subject = custom_subject or reason.get("subject")
        reason = reason.get("comments", "")

    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        print("[RevertWorkflow] No email recipients provided. Skipping email send.")
        return False
        
    requested_pic = get_pic_name(requested_by)
    smtp_server, smtp_port, sender_email, sender_password = get_smtp_settings()
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    stage_names = {
        "pending_bom": "BOM Verification",
        "pending_sourcing_and_cycle_time": "Sourcing & Cycle Time",
        "pending_costing": "Costing",
        "pending_npi": "NPI Verification",
        "pending_wi": "Work Instruction (WI)",
        "completed": "Completed Process"
    }
    
    from_stage_name = stage_names.get(from_stage, from_stage) or "Current Stage"
    to_stage_name = stage_names.get(to_stage, to_stage) or "Previous Stage"
    
    if custom_subject and str(custom_subject).strip():
        subject = str(custom_subject).strip()
    else:
        subject = f"[ContinuumX] Revert Request — RFQ {rfq_id} ({customer}) — Return to {to_stage_name}"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <div style="text-align: center; margin-bottom: 20px; background-color: #ffffff; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; display: block;">
            <img src="cid:continuumx_logo" alt="ContinuumX" style="width: 100%; max-width: 500px; height: auto; display: inline-block;" />
        </div>
        <div style="background-color: #2b6cb0; padding: 15px; border-radius: 6px 6px 0 0; color: white;">
            <h2 style="margin: 0; font-size: 18px;">🔄 RFQ Workflow Revert Notification</h2>
        </div>
        <div style="padding: 20px; background-color: #f7fafc;">
            <p>Dear Team,</p>
            <p>A workflow revert has been requested for the following RFQ:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 35%; border-bottom: 1px solid #edf2f7;">RFQ Number</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{rfq_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Customer</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{customer}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">From Stage</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #e53e3e; font-weight: bold;">{from_stage_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Returned To Stage</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #2b6cb0; font-weight: bold;">{to_stage_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Requested By</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{requested_pic}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Requested At</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{now_str}</td>
                </tr>
            </table>
            
            <div style="background-color: #ebf8ff; border-left: 4px solid #2b6cb0; padding: 12px; margin: 15px 0; border-radius: 4px;">
                <h4 style="margin: 0 0 5px 0; color: #2c5282;">Comments / Reason for Revert:</h4>
                <p style="margin: 0; font-style: italic;">{reason or '[No comments added]'}</p>
            </div>
            
            <p style="font-size: 12px; color: #718096; margin-top: 25px; border-top: 1px solid #e2e8f0; padding-top: 10px;">
                💡 <strong>Note on data continuity:</strong> All manually-entered pricing, supplier mappings, signatures, and photos have been preserved. You will be prompted to load this data upon re-opening the RFQ in your module.
            </p>
        </div>
        <div style="text-align: center; font-size: 11px; color: #a0aec0; margin-top: 15px;">
            This is an automated notification from the ContinuumX Agentic Platform.
        </div>
    </body>
    </html>
    """
    
    def _do_send_revert():
        try:
            to_list = []
            for r in (recipients if isinstance(recipients, list) else [recipients]):
                if r and isinstance(r, str):
                    email_str = r.strip() if "@" in r else get_user_email(r.strip())
                    if email_str and "@" in email_str and email_str not in to_list:
                        to_list.append(email_str)
                        
            cc_list = []
            for c in (cc_recipients or []):
                if c and isinstance(c, str):
                    email_str = c.strip() if "@" in c else get_user_email(c.strip())
                    if email_str and "@" in email_str and email_str not in to_list and email_str not in cc_list:
                        cc_list.append(email_str)

            if not to_list:
                print(f"[RevertWorkflow] No valid To email recipients resolved from '{recipients}'. Skipping email.")
                return

            server = get_smtp_connection(smtp_server, smtp_port, sender_email, sender_password)

            msg = MIMEMultipart('related')
            msg['From'] = f"ContinuumX System <{sender_email}>"
            msg['To'] = ", ".join(to_list)
            if cc_list:
                msg['Cc'] = ", ".join(cc_list)
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))
            attach_logo_if_exists(msg)

            server.sendmail(sender_email, to_list + cc_list, msg.as_string())
            server.quit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            
    import threading
    t = threading.Thread(target=_do_send_revert)
    t.daemon = True
    t.start()
    return True

def get_all_revert_pending():
    """Scans all BOM files to find those with active revert requests."""
    bom_data_dir, _, _ = get_paths()
    revert_list = []
    
    if not os.path.exists(bom_data_dir):
        return revert_list
        
    for root, dirs, files in os.walk(bom_data_dir):
        for file in files:
            if file.endswith('.json') and not file.endswith('metadata.json'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                    
                    revert_block = data.get("revert_pending")
                    if revert_block and not revert_block.get("acknowledged", False):
                        current_status = data.get("status", "pending_bom")
                        target_stage = revert_block.get("target_stage")
                        
                        # If the status has advanced beyond the target stage, consider it implicitly acknowledged
                        if current_status != target_stage:
                            try:
                                data["revert_pending"]["acknowledged"] = True
                                with open(filepath, 'w', encoding='utf-8') as wf:
                                    json.dump(data, wf, indent=4)
                            except Exception as ex:
                                print(f"[RevertWorkflow] Failed to auto-acknowledge status change: {ex}")
                            continue
                            
                        revert_list.append({
                            "RFQ": data.get("RFQ", file.replace('.json', '')),
                            "Customer": data.get("Customer", "Unknown"),
                            "target_stage": target_stage,
                            "reason": revert_block.get("reason"),
                            "requested_by": revert_block.get("requested_by"),
                            "requested_at": revert_block.get("requested_at"),
                            "follow_up_sent_at": revert_block.get("follow_up_sent_at"),
                            "filepath": filepath
                        })
                except Exception as e:
                    print(f"[RevertWorkflow] Error reading {file}: {e}")
                    
    return revert_list

def undo_revert(*args, **kwargs):
    """
    Restores the RFQ status back to its pre-reverted stage and clears the revert block.
    Supports both 2-positional (bom_filepath, requested_by) and 4-positional (rfq_id, customer, requested_by, bom_data_dir).
    """
    if len(args) >= 3 or "bom_data_dir" in kwargs or ("customer" in kwargs and "rfq_id" in kwargs):
        rfq_id = args[0] if len(args) > 0 else kwargs.get("rfq_id")
        customer = args[1] if len(args) > 1 else kwargs.get("customer")
        requested_by = args[2] if len(args) > 2 else kwargs.get("requested_by", "Module User")
        bom_data_dir = args[3] if len(args) > 3 else kwargs.get("bom_data_dir")
        bom_filepath = resolve_bom_filepath(rfq_id, customer, bom_data_dir)
    else:
        bom_filepath = args[0] if len(args) > 0 else kwargs.get("bom_filepath")
        requested_by = args[1] if len(args) > 1 else kwargs.get("requested_by", "Module User")
        if bom_filepath and not os.path.exists(bom_filepath):
            bom_filepath = resolve_bom_filepath(bom_filepath)

    if not bom_filepath or not os.path.exists(bom_filepath):
        return False, f"BOM file not found at: {bom_filepath or (args[0] if args else '')}"
        
    try:
        with open(bom_filepath, 'r', encoding='utf-8-sig') as f:
            bom_data = json.load(f)
            
        revert_block = bom_data.get("revert_pending")
        if not revert_block:
            return False, "No active revert pending found."
            
        pre_revert_stage = revert_block.get("pre_revert_stage")
        if not pre_revert_stage:
            return False, "No pre-reverted stage recorded."
            
        from_stage = bom_data.get("status", "pending_bom")
        now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        
        # Restore status
        bom_data["status"] = pre_revert_stage
        
        # Clear revert pending
        bom_data["revert_pending"] = None
        
        # Log to revert history
        if "revert_history" not in bom_data or not isinstance(bom_data["revert_history"], list):
            bom_data["revert_history"] = []
            
        bom_data["revert_history"].append({
            "timestamp": now_str,
            "requested_by": requested_by,
            "reason": "Undo Revert - Restored back to previous pending stage.",
            "from_stage": from_stage,
            "to_stage": pre_revert_stage,
            "is_undo": True
        })
        
        with open(bom_filepath, 'w', encoding='utf-8') as f:
            json.dump(bom_data, f, indent=4)
            
        return True, "Revert successfully undone and stage restored."
    except Exception as e:
        return False, f"Failed to undo revert: {e}"

def send_stuck_query_email(recipients, rfq_id, customer, stage_name, query_text, requested_by, cc_recipients=None):
    """
    Sends stuck stage inquiry email from SMTP settings.
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        print("[RevertWorkflow] No query recipients provided. Skipping email.")
        return False
        
    requested_by = get_pic_name(requested_by)
    smtp_server, smtp_port, sender_email, sender_password = get_smtp_settings()
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    subject = f"[ContinuumX] Stuck Stage Query — RFQ {rfq_id} ({customer}) — Action Required"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <div style="text-align: center; margin-bottom: 20px; background-color: #ffffff; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; display: block;">
            <img src="cid:continuumx_logo" alt="ContinuumX" style="width: 100%; max-width: 500px; height: auto; display: inline-block;" />
        </div>
        <div style="background-color: #d69e2e; padding: 15px; border-radius: 6px 6px 0 0; color: white;">
            <h2 style="margin: 0; font-size: 18px;">⚠️ Stuck Stage Query Notification</h2>
        </div>
        <div style="padding: 20px; background-color: #f7fafc;">
            <p>Dear PIC,</p>
            <p>An inquiry has been made regarding a pending project currently at your stage:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 35%; border-bottom: 1px solid #edf2f7;">RFQ Number</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{rfq_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Customer</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{customer}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Stuck Stage</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #d69e2e; font-weight: bold;">{stage_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Queried By</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{requested_by}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Sent At</td>
                    <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{now_str}</td>
                </tr>
            </table>
            
            <div style="background-color: #fffaf0; border-left: 4px solid #dd6b20; padding: 12px; margin: 15px 0; border-radius: 4px;">
                <h4 style="margin: 0 0 5px 0; color: #dd6b20;">Query Message:</h4>
                <p style="margin: 0; font-style: italic;">{query_text}</p>
            </div>
            
            <p>Please review and update the status or proceed with dispatch as soon as possible.</p>
        </div>
        <div style="text-align: center; font-size: 11px; color: #a0aec0; margin-top: 15px;">
            This is an automated query notification from the ContinuumX Agentic Platform.
        </div>
    </body>
    </html>
    """
    
    def _do_send_query():
        try:
            to_list = []
            for r in (recipients if isinstance(recipients, list) else [recipients]):
                if r and isinstance(r, str) and "@" in r and r.strip() not in to_list:
                    to_list.append(r.strip())
                    
            cc_list = []
            for c in (cc_recipients or []):
                if c and isinstance(c, str) and "@" in c and c.strip() not in to_list and c.strip() not in cc_list:
                    cc_list.append(c.strip())

            if not to_list:
                print("[RevertWorkflow] No valid To recipients provided. Skipping email.")
                return

            server = get_smtp_connection(smtp_server, smtp_port, sender_email, sender_password)

            msg = MIMEMultipart('related')
            msg['From'] = f"ContinuumX System <{sender_email}>"
            msg['To'] = ", ".join(to_list)
            if cc_list:
                msg['Cc'] = ", ".join(cc_list)
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))
            attach_logo_if_exists(msg)

            all_destinations = to_list + cc_list
            server.sendmail(sender_email, all_destinations, msg.as_string())
            print(f"[RevertWorkflow] Query email sent successfully to To:{to_list} CC:{cc_list}")
            server.quit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[RevertWorkflow] Failed to send query email: {e}")

    import threading
    threading.Thread(target=_do_send_query, daemon=True).start()
    return True

class EmailComposerDialog(tk.Toplevel):
    def __init__(self, parent, sender_name, sender_email, recipient_name, recipient_email, subject, body_template, default_cc=None, available_recipients=None):
        super().__init__(parent)
        self.parent = parent
        self.sender_name = sender_name
        self.sender_email = sender_email
        
        if isinstance(recipient_name, list):
            self.recipient_names = recipient_name
        else:
            self.recipient_names = [recipient_name] if recipient_name else []
            
        if isinstance(recipient_email, list):
            self.recipient_emails = recipient_email
        else:
            self.recipient_emails = [recipient_email] if recipient_email else []
            
        self.subject = subject
        self.body_template = body_template
        self.available_recipients = available_recipients or {}  # name -> email
        
        self.result = None  # None if cancelled, else dictionary of result
        self._skip_autofit = True
        
        self.title("Email Notification Composer")
        self.geometry("620x680")
        self.resizable(False, False)
        self.configure(bg='#EBF8FF')
        self.transient(parent)
        self.grab_set()
        
        # Heading
        tk.Label(self, text="Preview & Compose Notification Email", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg='#EBF8FF').pack(pady=(15, 10))
        
        # Grid frame for fields
        fields_frame = tk.Frame(self, bg='#EBF8FF')
        fields_frame.pack(fill='x', padx=20, pady=5)
        fields_frame.columnconfigure(1, weight=1)
        
        # From Row
        smtp_srv, smtp_prt, sys_email, _ = get_smtp_settings()
        disp_email = sys_email or sender_email or "system-notifications@continuumx.com.my"
        tk.Label(fields_frame, text="From:", font=("Segoe UI", 10, "bold"), bg='#EBF8FF', anchor='w').grid(row=0, column=0, sticky='w', pady=3, padx=(0, 10))
        from_text = f"ContinuumX System <{disp_email}>" if disp_email else "ContinuumX System"
        from_entry = tk.Entry(fields_frame, font=("Segoe UI", 10))
        from_entry.insert(0, from_text)
        from_entry.config(state='readonly')
        from_entry.grid(row=0, column=1, sticky='ew', pady=3)
        
        # To Row
        tk.Label(fields_frame, text="To List:", font=("Segoe UI", 10, "bold"), bg='#EBF8FF', anchor='nw').grid(row=1, column=0, sticky='nw', pady=3, padx=(0, 10))
        
        to_container = tk.Frame(fields_frame, bg='#EBF8FF')
        to_container.grid(row=1, column=1, sticky='ew', pady=3)
        to_container.columnconfigure(0, weight=1)

        self.to_listbox = tk.Listbox(to_container, font=("Segoe UI", 9), height=3, selectmode=tk.SINGLE)
        self.to_listbox.grid(row=0, column=0, sticky='ew')

        to_scroll = tk.Scrollbar(to_container, orient=tk.VERTICAL, command=self.to_listbox.yview)
        to_scroll.grid(row=0, column=1, sticky='ns')
        self.to_listbox.config(yscrollcommand=to_scroll.set)

        to_controls = tk.Frame(to_container, bg='#EBF8FF')
        to_controls.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(5, 0))
        to_controls.columnconfigure(0, weight=1)

        self.user_dir = get_user_directory()
        self.user_cc_options = []
        self.user_email_map = {}

        for u_name, u_info in self.user_dir.items():
            u_email = u_info.get("email", "").strip() if isinstance(u_info, dict) else str(u_info).strip()
            if not u_email:
                u_email = get_user_email(u_name)
            disp = f"{u_name} <{u_email}>" if u_email else u_name
            self.user_cc_options.append(disp)
            if u_email:
                self.user_email_map[disp] = u_email
                self.user_email_map[u_name] = u_email

        self.to_user_combo = ttk.Combobox(to_controls, values=self.user_cc_options, font=("Segoe UI", 9), state="normal")
        self.to_user_combo.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        if self.user_cc_options:
            self.to_user_combo.set(self.user_cc_options[0])

        to_add_btn = tk.Button(to_controls, text="➕ Add To", command=self.add_to_email, bg='#3182CE', fg='white', font=("Segoe UI", 8, "bold"), relief='flat')
        to_add_btn.grid(row=0, column=1, padx=2)

        to_remove_btn = tk.Button(to_controls, text="❌ Remove", command=self.remove_to_email, bg='#E53E3E', fg='white', font=("Segoe UI", 8, "bold"), relief='flat')
        to_remove_btn.grid(row=0, column=2, padx=2)

        # Pre-populate To listbox
        for name, email in zip(self.recipient_names, self.recipient_emails):
            disp = f"{name} <{email}>" if email else name
            self.to_listbox.insert(tk.END, disp)

        # CC Row
        tk.Label(fields_frame, text="CC List:", font=("Segoe UI", 10, "bold"), bg='#EBF8FF', anchor='nw').grid(row=2, column=0, sticky='nw', pady=3, padx=(0, 10))
        
        cc_container = tk.Frame(fields_frame, bg='#EBF8FF')
        cc_container.grid(row=2, column=1, sticky='ew', pady=3)
        cc_container.columnconfigure(0, weight=1)
        
        self.cc_listbox = tk.Listbox(cc_container, font=("Segoe UI", 9), height=3, selectmode=tk.SINGLE)
        self.cc_listbox.grid(row=0, column=0, sticky='ew')
        
        cc_scroll = tk.Scrollbar(cc_container, orient=tk.VERTICAL, command=self.cc_listbox.yview)
        cc_scroll.grid(row=0, column=1, sticky='ns')
        self.cc_listbox.config(yscrollcommand=cc_scroll.set)
        
        cc_controls = tk.Frame(cc_container, bg='#EBF8FF')
        cc_controls.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(5, 0))
        cc_controls.columnconfigure(0, weight=1)

        self.cc_user_combo = ttk.Combobox(cc_controls, values=self.user_cc_options, font=("Segoe UI", 9), state="normal")
        self.cc_user_combo.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        if self.user_cc_options:
            self.cc_user_combo.set(self.user_cc_options[0])

        add_btn = tk.Button(cc_controls, text="➕ Add CC", command=self.add_cc_email, bg='#3182CE', fg='white', font=("Segoe UI", 8, "bold"), relief='flat')
        add_btn.grid(row=0, column=1, padx=2)
        
        remove_btn = tk.Button(cc_controls, text="❌ Remove", command=self.remove_cc_email, bg='#E53E3E', fg='white', font=("Segoe UI", 8, "bold"), relief='flat')
        remove_btn.grid(row=0, column=2, padx=2)
        
        # Subject Row
        tk.Label(fields_frame, text="Subject:", font=("Segoe UI", 10, "bold"), bg='#EBF8FF', anchor='w').grid(row=3, column=0, sticky='w', pady=5, padx=(0, 10))
        self.sub_entry = tk.Entry(fields_frame, font=("Segoe UI", 10))
        self.sub_entry.insert(0, subject)
        self.sub_entry.grid(row=3, column=1, sticky='ew', pady=5)
        
        # Comments Row
        is_revert = "revert" in subject.lower()
        lbl_text = "Add Revert Reason (Required) *:" if is_revert else "Add Comments:"
        fg_color = "#C53030" if is_revert else "#1A365D"
        tk.Label(self, text=lbl_text, font=("Segoe UI", 10, "bold"), fg=fg_color, bg='#EBF8FF', anchor='w').pack(anchor='w', padx=20, pady=(10, 2))
        self.comments_text = tk.Text(self, height=2, font=("Segoe UI", 10))
        self.comments_text.pack(fill='x', padx=20, pady=2)
        self.comments_text.bind("<KeyRelease>", lambda e: self.update_preview())
        
        # Preview Header
        tk.Label(self, text="Email Body Preview (Read-Only):", font=("Segoe UI", 10, "bold"), bg='#EBF8FF', anchor='w').pack(anchor='w', padx=20, pady=(10, 2))
        
        preview_container = tk.Frame(self)
        preview_container.pack(fill='both', expand=True, padx=20, pady=2)
        sb = tk.Scrollbar(preview_container)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preview_area = tk.Text(preview_container, wrap='word', font=("Consolas", 9), yscrollcommand=sb.set, height=8)
        self.preview_area.pack(side=tk.LEFT, fill='both', expand=True)
        sb.config(command=self.preview_area.yview)
        
        # OK / Cancel Buttons
        btn_frame = tk.Frame(self, bg='#EBF8FF', pady=15)
        btn_frame.pack(fill='x')
        
        tk.Button(btn_frame, text="Send Email", command=self.on_send, width=15, bg='#2B6CB0', fg='white', font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=10).pack(side=tk.RIGHT)
        
        if default_cc:
            smtp_srv, smtp_prt, sys_email, _ = get_smtp_settings()
            sender_em_lower = (disp_email or "").lower()
            for item in default_cc:
                if item and str(item).strip():
                    raw_item = str(item).strip()
                    resolved_em = get_user_email(raw_item)
                    matched_disp = None
                    for disp in self.user_cc_options:
                        if raw_item.lower() in disp.lower() or (resolved_em and resolved_em.lower() in disp.lower()):
                            matched_disp = disp
                            break
                    target_disp = matched_disp or (f"{raw_item} <{resolved_em}>" if resolved_em else raw_item)
                    
                    if resolved_em and resolved_em.lower() == sender_em_lower:
                        continue

                    existing_in_cc = [self.cc_listbox.get(i).lower() for i in range(self.cc_listbox.size())]
                    if target_disp.lower() not in existing_in_cc:
                        self.cc_listbox.insert(tk.END, target_disp)
        self.update_preview()
        
        # Center the dialog
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            self.geometry("+300+300")

    def add_to_email(self):
        val = self.to_user_combo.get().strip() if hasattr(self, 'to_user_combo') else ""
        if not val: return
        target_disp = val
        if hasattr(self, 'user_email_map') and val in self.user_email_map:
            target_disp = val
        elif '@' in val and '.' in val.split('@')[-1]:
            target_disp = val
        else:
            resolved_em = get_user_email(val)
            target_disp = f"{val} <{resolved_em}>" if resolved_em else val

        existing = [self.to_listbox.get(i).lower() for i in range(self.to_listbox.size())]
        if target_disp.lower() in existing:
            messagebox.showinfo("Duplicate", "This user/email is already in the To list.", parent=self)
            return
        self.to_listbox.insert(tk.END, target_disp)
        self.to_user_combo.set('')

    def remove_to_email(self):
        sel = self.to_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an email from the To list to remove.", parent=self)
            return
        for idx in reversed(sel):
            self.to_listbox.delete(idx)
            
    def add_cc_email(self):
        val = self.cc_user_combo.get().strip() if hasattr(self, 'cc_user_combo') else ""
        if not val: return
        target_disp = val
        if hasattr(self, 'user_email_map') and val in self.user_email_map:
            target_disp = val
        elif '@' in val and '.' in val.split('@')[-1]:
            target_disp = val
        else:
            resolved_em = get_user_email(val)
            target_disp = f"{val} <{resolved_em}>" if resolved_em else val

        existing = [self.cc_listbox.get(i).lower() for i in range(self.cc_listbox.size())]
        if target_disp.lower() in existing:
            messagebox.showinfo("Duplicate", "This user/email is already in the CC list.", parent=self)
            return
        self.cc_listbox.insert(tk.END, target_disp)
        self.cc_user_combo.set('')

    def remove_cc_email(self):
        sel = self.cc_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an email from the CC list to remove.", parent=self)
            return
        for idx in reversed(sel):
            self.cc_listbox.delete(idx)

    def update_preview(self):
        comments = self.comments_text.get("1.0", tk.END).strip()
        if not comments:
            comments = "[No comments added]"
            
        raw_to_items = list(self.to_listbox.get(0, tk.END)) if hasattr(self, 'to_listbox') else []
        to_names = []
        for item in raw_to_items:
            name = item.split("<")[0].strip() if "<" in item else item.strip()
            if name: to_names.append(name)

        if to_names:
            to_line = " & ".join(to_names)
        else:
            to_line = "Team"
            
        full_body = self.body_template.format(recipient=to_line, comments=comments)
        
        self.preview_area.config(state='normal')
        self.preview_area.delete("1.0", tk.END)
        self.preview_area.insert("1.0", full_body)
        self.preview_area.config(state='disabled')

    def on_send(self):
        raw_to_items = list(self.to_listbox.get(0, tk.END))
        to_emails = []
        for item in raw_to_items:
            if "<" in item and ">" in item:
                em = item.split("<")[-1].split(">")[0].strip()
                if em: to_emails.append(em)
            else:
                to_emails.append(item.strip())

        if not to_emails:
            messagebox.showwarning("Recipient Required", "Please specify at least one 'To' recipient.", parent=self)
            return

        raw_cc_items = list(self.cc_listbox.get(0, tk.END))
        cc_emails = []
        for item in raw_cc_items:
            if "<" in item and ">" in item:
                em = item.split("<")[-1].split(">")[0].strip()
                if em: cc_emails.append(em)
            else:
                cc_emails.append(item.strip())

        comments = self.comments_text.get("1.0", tk.END).strip()
        is_revert = "revert" in self.subject.lower()
        if is_revert and not comments:
            messagebox.showwarning(
                "Revert Reason Required",
                "Please enter a reason for reverting this RFQ in the 'Add Revert Reason' box before sending.",
                parent=self
            )
            self.comments_text.focus_set()
            return

        custom_subject = self.sub_entry.get().strip() if hasattr(self, 'sub_entry') else self.subject
        self.result = {
            "to_emails": to_emails,
            "cc_emails": cc_emails,
            "comments": comments,
            "subject": custom_subject
        }
        self.destroy()



def send_dispatch_email(recipients, rfq_id, customer, from_stage, to_stage, comments, dispatched_by, cc_recipients=None, subject=None, bulk_rfqs=None):
    if isinstance(recipients, str):
        recipients = [recipients]
    if not recipients:
        print("[RevertWorkflow] No dispatch recipients provided. Skipping email.")
        return False

    def _do_send_email():
        try:
            dispatched_pic = get_pic_name(dispatched_by)
            smtp_server, smtp_port, sender_email, sender_password = get_smtp_settings()
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

            if subject and str(subject).strip():
                email_subject = str(subject).strip()
            elif bulk_rfqs and isinstance(bulk_rfqs, list) and len(bulk_rfqs) > 1:
                email_subject = f"[ContinuumX] Batch RFQ Dispatch Notification — {len(bulk_rfqs)} RFQs Dispatched to {to_stage}"
            else:
                email_subject = f"[ContinuumX] RFQ Dispatch Notification — RFQ {rfq_id} ({customer}) — {from_stage} Completed"

            if bulk_rfqs and isinstance(bulk_rfqs, list) and len(bulk_rfqs) > 1:
                table_rows = ""
                for idx, r_item in enumerate(bulk_rfqs, 1):
                    r_id = r_item.get("rfq_id", "")
                    c_name = r_item.get("customer", "")
                    assys = r_item.get("assemblies", "")
                    if isinstance(assys, list):
                        assys = ", ".join(str(a) for a in assys)
                    table_rows += f"""
                    <tr>
                        <td style="padding: 8px; border: 1px solid #edf2f7; text-align: center;">{idx}</td>
                        <td style="padding: 8px; border: 1px solid #edf2f7; font-weight: bold; color: #2b6cb0;">{r_id}</td>
                        <td style="padding: 8px; border: 1px solid #edf2f7;">{c_name}</td>
                        <td style="padding: 8px; border: 1px solid #edf2f7;">{assys or 'Standard'}</td>
                    </tr>
                    """

                rfq_content_html = f"""
                <p>The following <strong>{len(bulk_rfqs)} RFQs</strong> have been batch completed and dispatched to the next stage:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #2b6cb0; color: white;">
                            <th style="padding: 8px; border: 1px solid #cbd5e0; width: 8%;">#</th>
                            <th style="padding: 8px; border: 1px solid #cbd5e0; width: 27%;">RFQ Number</th>
                            <th style="padding: 8px; border: 1px solid #cbd5e0; width: 30%;">Customer</th>
                            <th style="padding: 8px; border: 1px solid #cbd5e0; width: 35%;">Assemblies / Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold; width: 35%; border-bottom: 1px solid #edf2f7;">From Stage</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #e53e3e; font-weight: bold;">{from_stage}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Sent To Stage</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #38a169; font-weight: bold;">{to_stage}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Dispatched By</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{dispatched_pic}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Dispatched At</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{now_str}</td>
                    </tr>
                </table>
                """
            else:
                rfq_content_html = f"""
                <p>The RFQ has been successfully dispatched to the next stage:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold; width: 35%; border-bottom: 1px solid #edf2f7;">RFQ Number</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">{rfq_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Customer</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{customer}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">From Stage</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #e53e3e; font-weight: bold;">{from_stage}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Sent To Stage</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; color: #38a169; font-weight: bold;">{to_stage}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Dispatched By</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{dispatched_pic}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #edf2f7;">Dispatched At</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{now_str}</td>
                    </tr>
                </table>
                """

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 650px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 20px; background-color: #ffffff; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; display: block;">
                    <img src="cid:continuumx_logo" alt="ContinuumX" style="width: 100%; max-width: 500px; height: auto; display: inline-block;" />
                </div>
                <div style="background-color: #2f855a; padding: 15px; border-radius: 6px 6px 0 0; color: white;">
                    <h2 style="margin: 0; font-size: 18px;">🚀 RFQ Workflow Dispatch Notification</h2>
                </div>
                <div style="padding: 20px; background-color: #f7fafc;">
                    <p>Dear Team,</p>
                    {rfq_content_html}
                    <div style="background-color: #f0fff4; border-left: 4px solid #38a169; padding: 12px; margin: 15px 0; border-radius: 4px;">
                        <h4 style="margin: 0 0 5px 0; color: #2f855a;">Comments / Message:</h4>
                        <p style="margin: 0; font-style: italic;">{comments}</p>
                    </div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #a0aec0; margin-top: 15px;">
                    This is an automated notification from the ContinuumX Agentic Platform.
                </div>
            </body>
            </html>
            """
            
            to_list = []
            for r in (recipients if isinstance(recipients, list) else [recipients]):
                if r and isinstance(r, str):
                    email_str = r.strip() if "@" in r else get_user_email(r.strip())
                    if email_str and "@" in email_str and email_str not in to_list:
                        to_list.append(email_str)
                        
            cc_list = []
            for c in (cc_recipients or []):
                if c and isinstance(c, str):
                    email_str = c.strip() if "@" in c else get_user_email(c.strip())
                    if email_str and "@" in email_str and email_str not in to_list and email_str not in cc_list:
                        cc_list.append(email_str)

            if not to_list:
                print(f"[RevertWorkflow] No valid To email recipients resolved from '{recipients}'. Skipping email.")
                return

            server = get_smtp_connection(smtp_server, smtp_port, sender_email, sender_password)

            msg = MIMEMultipart('related')
            msg['From'] = f"ContinuumX System <{sender_email}>"
            msg['To'] = ", ".join(to_list)
            if cc_list:
                msg['Cc'] = ", ".join(cc_list)
            msg['Subject'] = email_subject
            msg.attach(MIMEText(html_body, 'html'))
            attach_logo_if_exists(msg)

            all_destinations = to_list + cc_list
            server.sendmail(sender_email, all_destinations, msg.as_string())
            print(f"[RevertWorkflow] Dispatch notification email sent successfully to To:{to_list} CC:{cc_list}")
            server.quit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[RevertWorkflow] Failed to send dispatch email: {e}")

    import threading
    threading.Thread(target=_do_send_email, daemon=True).start()
    return True

def get_pic_name(username):
    if not username:
        return "System Administrator"
    if username.lower() == "admin":
        return "Ai Tink"
        
    # Check case-insensitive match in user directory
    try:
        user_dir = get_user_directory()
        for name in user_dir.keys():
            if name.lower() == username.lower():
                return name
    except:
        pass
            
    # Fallback to signatures.json check
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sig_file = os.path.normpath(os.path.join(current_dir, "..", "WI", "Master Data", "signatures.json"))
    if os.path.exists(sig_file):
        try:
            with open(sig_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name in data.keys():
                    if name.lower() == username.lower():
                        return name
        except:
            pass
            
    # Capitalize first letter of each word as fallback
    return username.title()

def resolve_assigned_pics(data, status=None):
    """
    Dynamically resolves all PIC name(s) who modified or are responsible for the RFQ.
    Preserves all previous amending PIC names chronologically and joins them with comma (,).
    """
    if not isinstance(data, dict):
        return "Unassigned"
        
    pics = []
    status = status or data.get("status") or "pending_bom"
    
    # 1. Inspect stage-specific fields
    if status == "pending_bom":
        p = data.get("bom_assigned_by") or data.get("dispatched_by")
        if p: pics.append(p)
    elif status == "pending_sourcing_and_cycle_time":
        s_pic = data.get("sourcing_assigned_by") or data.get("sourcing_dispatched_by")
        c_pic = data.get("cycle_time_assigned_by") or data.get("cycle_time_dispatched_by")
        if s_pic: pics.append(s_pic)
        if c_pic and c_pic not in pics: pics.append(c_pic)
    elif status == "pending_costing":
        p = data.get("costing_assigned_by") or data.get("costing_dispatched_by")
        if p: pics.append(p)
    elif status == "pending_npi":
        p = data.get("npi_assigned_by") or data.get("npi_dispatched_by")
        if p: pics.append(p)
    elif status == "pending_wi":
        p = data.get("wi_assigned_by") or data.get("wi_dispatched_by")
        if p: pics.append(p)

    # 2. Check history logs in data for active users ("Changed By", "user", "requested_by", "dispatched_by")
    history = data.get("history", []) or data.get("audit_trail", []) or data.get("revert_history", [])
    for entry in history:
        if isinstance(entry, dict):
            stg = entry.get("stage") or entry.get("target_stage") or entry.get("from_stage")
            u = entry.get("Changed By") or entry.get("user") or entry.get("requested_by") or entry.get("dispatched_by")
            if u:
                if not stg or stg == status or status == "pending_bom" or not pics:
                    if u not in pics:
                        pics.append(u)

    # 3. Fallback to default configured PICs for that stage from system_pics.json
    if not pics:
        config = get_system_pics(status)
        default_pics = config.get("to", []) + config.get("cc", [])
        for d in default_pics:
            if d and d not in pics:
                pics.append(d)

    # Map login usernames to display PIC names
    resolved = []
    for p in pics:
        real_p = get_pic_name(p)
        if real_p and real_p not in resolved:
            resolved.append(real_p)

    if not resolved:
        return "Unassigned"
    else:
        return ", ".join(resolved)

def attach_logo_if_exists(msg):
    from email.mime.image import MIMEImage
    import io
    
    server_path = _get_central_server_path()
    base_dir = _ensure_launcher_path()

    logo_path = None
    try:
        from config import LOGO_HORIZONTAL_DARK_PATH
        if LOGO_HORIZONTAL_DARK_PATH and os.path.exists(LOGO_HORIZONTAL_DARK_PATH):
            logo_path = LOGO_HORIZONTAL_DARK_PATH
    except Exception:
        pass

    if not logo_path:
        try:
            from config import LOGO_PATH
            if LOGO_PATH and os.path.exists(LOGO_PATH):
                logo_path = LOGO_PATH
        except Exception:
            pass

    if not logo_path or not os.path.exists(logo_path):
        logo_names = [
            "logo_horizontal_dark.png",
            "logo_horizontal_light.png",
            "logo_profile_dark.png",
            "logo_profile_light.png",
            "logo.png",
            "ContinuumX.png",
            "Contunuum X logo_Lettermark_Gradient (Dark).png",
            "Contunuum X logo_Lettermark_Gradient (Light).png"
        ]

        search_dirs = [
            os.path.join(server_path, "assets", "images"),
            os.path.join(server_path, "assets"),
            os.path.join(server_path, "ContinuumX Logo"),
            server_path,
            os.path.join(base_dir, "assets", "images"),
            os.path.join(base_dir, "assets"),
            os.path.normpath(os.path.join(base_dir, "..", "assets", "images")),
            os.path.normpath(os.path.join(base_dir, "..", "..", "assets", "images")),
        ]

        for s_dir in search_dirs:
            if s_dir and os.path.exists(s_dir):
                for l_name in logo_names:
                    cand = os.path.normpath(os.path.join(s_dir, l_name))
                    if os.path.exists(cand):
                        logo_path = cand
                        break
                if logo_path:
                    break

    if not logo_path or not os.path.exists(logo_path):
        assets_dir = os.path.join(server_path, "assets")
        if os.path.exists(assets_dir):
            for root_dir, _, files in os.walk(assets_dir):
                for fname in files:
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico')):
                        if 'logo' in fname.lower() or 'continuum' in fname.lower():
                            logo_path = os.path.join(root_dir, fname)
                            break
                if logo_path:
                    break


    if logo_path and os.path.exists(logo_path):
        try:
            from PIL import Image
            img = Image.open(logo_path)
            bbox = img.getbbox()
            cropped = img.crop(bbox) if bbox else img
            
            # Create a solid white background with padding so it renders clearly in both Light and Dark mode
            pad_x, pad_y = 60, 40
            bg = Image.new("RGB", (cropped.width + pad_x * 2, cropped.height + pad_y * 2), (255, 255, 255))
            if cropped.mode in ('RGBA', 'LA') or (cropped.mode == 'P' and 'transparency' in cropped.info):
                bg.paste(cropped, (pad_x, pad_y), cropped)
            else:
                bg.paste(cropped, (pad_x, pad_y))
                
            buf = io.BytesIO()
            bg.save(buf, format="PNG")
            img_data = buf.getvalue()
            
            msg_image = MIMEImage(img_data)
            msg_image.add_header('Content-ID', '<continuumx_logo>')
            msg_image.add_header('Content-Disposition', 'inline', filename='logo.png')
            msg.attach(msg_image)
            print("[RevertWorkflow] Auto-cropped white-banner inline logo attached successfully.")
            return
        except Exception as e:
            print(f"[RevertWorkflow] PIL logo processing error: {e}. Falling back to raw file attach.")
            try:
                with open(logo_path, 'rb') as f:
                    img_data = f.read()
                msg_image = MIMEImage(img_data)
                msg_image.add_header('Content-ID', '<continuumx_logo>')
                msg_image.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg.attach(msg_image)
            except Exception as ex:
                print(f"[RevertWorkflow] Raw logo attach failed: {ex}")
    else:
        print(f"[RevertWorkflow] Logo path does not exist: {logo_path}")

def get_system_pics(stage_code):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Priority locations for system_pics.json (Project Management AppData first from config.ini, then local module dir)
    _, _, pm_appdata_dir = get_paths()
    pm_pics_path = os.path.normpath(os.path.join(pm_appdata_dir, "system_pics.json"))
    local_pics_path = os.path.normpath(os.path.join(current_dir, "system_pics.json"))
    
    candidate_paths = [pm_pics_path, local_pics_path]
    
    # Standard fallbacks matching query_pic_workflow/reverts
    fallbacks = {
        "pending_bom": {"to": ["admin"], "cc": []},
        "pending_sourcing_and_cycle_time": {"to": ["JT Tang", "ML Lim"], "cc": []},
        "pending_sourcing": {"to": ["JT Tang"], "cc": []},
        "pending_cycle_time": {"to": ["ML Lim"], "cc": []},
        "pending_costing": {"to": ["ML Lim"], "cc": []},
        "pending_npi": {"to": ["PH Ang"], "cc": []},
        "pending_wi": {"to": ["HC Chan"], "cc": []},
        "completed": {"to": ["System Administrator"], "cc": []}
    }
    
    for pics_file in candidate_paths:
        if os.path.exists(pics_file):
            try:
                with open(pics_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    if stage_code in data:
                        res = data[stage_code]
                        if isinstance(res, dict):
                            return {
                                "to": res.get("to", []),
                                "cc": res.get("cc", [])
                            }
                        elif isinstance(res, list):
                            return {"to": res, "cc": []}
            except Exception as e:
                print(f"[RevertWorkflow] Error reading system_pics.json from {pics_file}: {e}")
            
    return fallbacks.get(stage_code, {"to": ["admin"], "cc": []})

def save_system_pics(pics_dict):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    _, _, pm_appdata_dir = get_paths()
    pm_pics_path = os.path.normpath(os.path.join(pm_appdata_dir, "system_pics.json"))
    local_pics_path = os.path.normpath(os.path.join(current_dir, "system_pics.json"))
    
    # Try saving to PM Server AppData first
    target_files = [pm_pics_path, local_pics_path]
    success_any = False
    for target in target_files:
        try:
            parent_dir = os.path.dirname(target)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                json.dump(pics_dict, f, indent=4)
            success_any = True
        except Exception as e:
            print(f"[RevertWorkflow] Error saving system_pics.json to {target}: {e}")
    return success_any

class MaintainSystemPICsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("System User Configuration")
        self._skip_autofit = True
        self.geometry("750x600")
        self.configure(bg="#EBF8FF")
        self.transient(parent)
        self.grab_set()

        self.user_dir = get_user_directory()
        self.available_users = sorted(list(self.user_dir.keys()))

        self.pics_data = {}
        stages = ["pending_bom", "pending_sourcing_and_cycle_time", "pending_sourcing", "pending_cycle_time", "pending_costing", "pending_npi", "pending_wi", "completed"]
        for stg in stages:
            self.pics_data[stg] = get_system_pics(stg)

        header = tk.Frame(self, bg="#1A365D")
        header.pack(fill="x", side="top")
        tk.Label(header, text="Maintain System Users & CCs", font=("Segoe UI", 14, "bold"), fg="white", bg="#1A365D", pady=12).pack(side="left", padx=20)

        top_f = tk.Frame(self, bg="#EBF8FF")
        top_f.pack(fill="x", padx=20, pady=5)
        
        tk.Label(top_f, text="Select System Stage:", font=("Segoe UI", 10, "bold"), bg="#EBF8FF").pack(side="left", padx=5)
        
        self.stage_names_map = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Sourcing & Cycle Time (Combined)",
            "pending_sourcing": "Sourcing PICs",
            "pending_cycle_time": "Cycle Time PICs",
            "pending_costing": "Costing",
            "pending_npi": "NPI Verification",
            "pending_wi": "Work Instruction (WI)",
            "completed": "Completed"
        }
        self.stage_codes_map = {v: k for k, v in self.stage_names_map.items()}
        
        self.stage_var = tk.StringVar(value="BOM Verification")
        self.stage_cb = ttk.Combobox(top_f, textvariable=self.stage_var, values=list(self.stage_names_map.values()), state="readonly", width=35, font=("Segoe UI", 10))
        self.stage_cb.pack(side="left", padx=10)
        self.stage_cb.bind("<<ComboboxSelected>>", lambda e: self.on_stage_changed())

        cols_frame = tk.Frame(self, bg="#EBF8FF")
        cols_frame.pack(fill="both", expand=True, padx=20, pady=10)
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)
        # COLUMN 0: TO Users
        to_f = tk.LabelFrame(cols_frame, text=" Default To Users (Action Owners) ", font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D", padx=10, pady=10)
        to_f.grid(row=0, column=0, sticky="nsew", padx=5)
        to_f.rowconfigure(0, weight=1)
        to_f.columnconfigure(0, weight=1)
        
        self.to_listbox = tk.Listbox(to_f, font=("Segoe UI", 10), height=10, selectmode=tk.SINGLE)
        self.to_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        
        to_scroll = ttk.Scrollbar(to_f, orient="vertical", command=self.to_listbox.yview)
        to_scroll.grid(row=0, column=2, sticky="ns")
        self.to_listbox.config(yscrollcommand=to_scroll.set)
        
        self.to_user_var = tk.StringVar()
        self.to_user_cb = ttk.Combobox(to_f, textvariable=self.to_user_var, values=self.available_users, state="readonly", width=18)
        self.to_user_cb.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        if self.available_users:
            self.to_user_cb.current(0)
            
        to_add_btn = tk.Button(to_f, text="➕ Add To", command=self.add_to_pic, bg='#3182CE', fg='white', font=("Segoe UI", 9, "bold"), relief='flat')
        to_add_btn.grid(row=1, column=1, padx=5, pady=(10, 0))
        
        to_rem_btn = tk.Button(to_f, text="❌ Remove", command=self.remove_to_pic, bg='#E53E3E', fg='white', font=("Segoe UI", 9, "bold"), relief='flat')
        to_rem_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
 
        # COLUMN 1: CC Users
        cc_f = tk.LabelFrame(cols_frame, text=" Default CC Users (Keep in Loop) ", font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D", padx=10, pady=10)
        cc_f.grid(row=0, column=1, sticky="nsew", padx=5)
        cc_f.rowconfigure(0, weight=1)
        cc_f.columnconfigure(0, weight=1)
        
        self.cc_listbox = tk.Listbox(cc_f, font=("Segoe UI", 10), height=10, selectmode=tk.SINGLE)
        self.cc_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        
        cc_scroll = ttk.Scrollbar(cc_f, orient="vertical", command=self.cc_listbox.yview)
        cc_scroll.grid(row=0, column=2, sticky="ns")
        self.cc_listbox.config(yscrollcommand=cc_scroll.set)
        
        self.cc_user_var = tk.StringVar()
        self.cc_user_cb = ttk.Combobox(cc_f, textvariable=self.cc_user_var, values=self.available_users, state="readonly", width=18)
        self.cc_user_cb.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        if self.available_users:
            self.cc_user_cb.current(0)
            
        cc_add_btn = tk.Button(cc_f, text="➕ Add CC", command=self.add_cc_pic, bg='#3182CE', fg='white', font=("Segoe UI", 9, "bold"), relief='flat')
        cc_add_btn.grid(row=1, column=1, padx=5, pady=(10, 0))
        
        cc_rem_btn = tk.Button(cc_f, text="❌ Remove", command=self.remove_cc_pic, bg='#E53E3E', fg='white', font=("Segoe UI", 9, "bold"), relief='flat')
        cc_rem_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

        bot_f = tk.Frame(self, bg="#EBF8FF", pady=15)
        bot_f.pack(fill="x")
        
        tk.Button(bot_f, text="Save Configuration", command=self.on_save, width=20, bg='#2ead4e', fg='white', font=("Segoe UI", 10, "bold"), relief='flat').pack(side=tk.RIGHT, padx=20)
        tk.Button(bot_f, text="Cancel", command=self.destroy, width=12).pack(side=tk.RIGHT)

        self.on_stage_changed()

    def get_current_stage_code(self):
        return self.stage_codes_map[self.stage_var.get()]

    def on_stage_changed(self):
        self.to_listbox.delete(0, tk.END)
        self.cc_listbox.delete(0, tk.END)
        
        stg = self.get_current_stage_code()
        pics = self.pics_data.get(stg, {"to": [], "cc": []})
        
        for name in pics.get("to", []):
            self.to_listbox.insert(tk.END, name)
        for name in pics.get("cc", []):
            self.cc_listbox.insert(tk.END, name)

    def add_to_pic(self):
        name = self.to_user_var.get()
        if not name: return
        existing = self.to_listbox.get(0, tk.END)
        if name in existing:
            messagebox.showinfo("Duplicate", f"'{name}' is already a To User for this stage.", parent=self)
            return
        self.to_listbox.insert(tk.END, name)
        stg = self.get_current_stage_code()
        self.pics_data[stg]["to"] = list(self.to_listbox.get(0, tk.END))

    def remove_to_pic(self):
        sel = self.to_listbox.curselection()
        if not sel: return
        self.to_listbox.delete(sel[0])
        stg = self.get_current_stage_code()
        self.pics_data[stg]["to"] = list(self.to_listbox.get(0, tk.END))

    def add_cc_pic(self):
        name = self.cc_user_var.get()
        if not name: return
        existing = self.cc_listbox.get(0, tk.END)
        if name in existing:
            messagebox.showinfo("Duplicate", f"'{name}' is already a CC User for this stage.", parent=self)
            return
        self.cc_listbox.insert(tk.END, name)
        stg = self.get_current_stage_code()
        self.pics_data[stg]["cc"] = list(self.cc_listbox.get(0, tk.END))

    def remove_cc_pic(self):
        sel = self.cc_listbox.curselection()
        if not sel: return
        self.cc_listbox.delete(sel[0])
        stg = self.get_current_stage_code()
        self.pics_data[stg]["cc"] = list(self.cc_listbox.get(0, tk.END))

    def on_save(self):
        if save_system_pics(self.pics_data):
            messagebox.showinfo("Success", "System User configuration saved successfully!", parent=self)
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to save System User configuration.", parent=self)

class SemanticDialog(tk.Toplevel):
    def __init__(self, master, title, message, is_yesno=False):
        if master:
            try: master.update_idletasks()
            except: pass
            
        if master is None or master == tk._default_root:
            root = tk._default_root
            if root:
                toplevels = [
                    w for w in root.winfo_children() 
                    if isinstance(w, tk.Toplevel) 
                    and w.winfo_viewable() 
                    and w.__class__.__name__ not in ("SemanticDialog", "SourcingStatusWindow", "SourcingOptionDetailDialog")
                ]
                if toplevels:
                    try:
                        toplevels.sort(key=lambda w: w.winfo_width() * w.winfo_height(), reverse=True)
                        master = toplevels[0]
                    except:
                        master = toplevels[-1]
                else:
                    master = root
            else:
                master = tk._default_root
                
        super().__init__(master)
        self._skip_autofit = True
        
        t = str(title).upper()
        if "SUCCESS" in t:
            self.theme = "success"
        elif "WARNING" in t or "DELETE" in t or "SELECTION" in t:
            self.theme = "warning"
        elif "ERROR" in t:
            self.theme = "error"
        else:
            self.theme = "info"
            
        THEMES = {
            "info": {"header_bg": "#dcedf5", "header_fg": "#1A365D", "btn_bg": "#1A365D"},
            "warning": {"header_bg": "#fff3cd", "header_fg": "#856404", "btn_bg": "#1A365D"},
            "error": {"header_bg": "#f8d7da", "header_fg": "#721c24", "btn_bg": "#dc3545"},
            "success": {"header_bg": "#d4edda", "header_fg": "#155724", "btn_bg": "#1A365D"}
        }
        colors = THEMES[self.theme]
        
        self.title(title)
        if master and master.winfo_viewable():
            try: self.transient(master)
            except: pass
        self.result = False
        
        self.configure(bg="#EBF8FF")
        
        header_frame = tk.Frame(self, bg=colors["header_bg"], bd=1, relief="solid")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        header_label = tk.Label(header_frame, text=t, font=("Segoe UI", 11, "bold"), bg=colors["header_bg"], fg=colors["header_fg"])
        header_label.pack(pady=8)
        
        content_frame = tk.Frame(self, bg="#EBF8FF", bd=0)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        msg_label = tk.Label(content_frame, text=message, font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D", justify="left", wraplength=350)
        msg_label.pack(padx=20, pady=20)
        
        btn_frame = tk.Frame(self, bg="#EBF8FF")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        confirm_text = "Proceed" if is_yesno else "OK"
        if self.theme == "error": confirm_text = "Close"
        if "SELECTION" in t: confirm_text = "Understood"
        
        self.cancel_btn = None
        if is_yesno:
            cancel_btn = tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10, bg="#E2E8F0", fg="#2D3748", font=("Segoe UI", 10), activebackground="#CBD5E0", activeforeground="#2D3748", relief="flat", bd=0, cursor="hand2")
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(bg="#CBD5E0", fg="#2D3748"))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(bg="#E2E8F0", fg="#2D3748"))
            cancel_btn.bind("<FocusIn>", lambda e: cancel_btn.configure(bg="#CBD5E0", fg="#2D3748"))
            cancel_btn.bind("<FocusOut>", lambda e: cancel_btn.configure(bg="#E2E8F0", fg="#2D3748"))
            cancel_btn.bind("<Return>", lambda e: self._on_cancel_event(e))
            cancel_btn.pack(side="left")
            self.cancel_btn = cancel_btn
            
        confirm_btn = tk.Button(btn_frame, text=confirm_text, command=self._on_confirm, width=10, bg=colors["btn_bg"], fg="white", font=("Segoe UI", 10, "bold"), activebackground="#0077B6" if colors["btn_bg"] == "#1A365D" else "#c82333", relief="flat", bd=0, cursor="hand2")
        c_bg = colors["btn_bg"]
        c_hbg = "#0077B6" if colors["btn_bg"] == "#1A365D" else "#c82333"
        confirm_btn.bind("<Enter>", lambda e: confirm_btn.configure(bg=c_hbg))
        confirm_btn.bind("<Leave>", lambda e: confirm_btn.configure(bg=c_bg))
        confirm_btn.bind("<FocusIn>", lambda e: confirm_btn.configure(bg=c_hbg))
        confirm_btn.bind("<FocusOut>", lambda e: confirm_btn.configure(bg=c_bg))
        confirm_btn.bind("<Return>", lambda e: self._on_confirm_event(e))
        confirm_btn.pack(side="right")
        self.confirm_btn = confirm_btn

        self.bind("<Return>", lambda e: self._on_confirm())
        self.bind("<Left>", lambda e: self._focus_cancel())
        self.bind("<Right>", lambda e: self._focus_confirm())
        
        self.withdraw()
        self._center_on_master()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _focus_cancel(self):
        if self.cancel_btn:
            self.cancel_btn.focus_set()

    def _focus_confirm(self):
        if self.confirm_btn:
            self.confirm_btn.focus_set()

    def _on_cancel_event(self, event):
        self._on_cancel()
        return "break"

    def _on_confirm_event(self, event):
        self._on_confirm()
        return "break"

    def show(self):
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        try: self.update_idletasks()
        except: pass
        try: self.grab_set()
        except: pass
        if self.confirm_btn:
            self.confirm_btn.focus_set()
        else:
            self.focus_force()
        self.wait_window()
        return self.result

    def _center_on_master(self):
        try: self.update_idletasks()
        except: pass
        master = self.master
        if master and master.winfo_exists() and master.winfo_viewable() and master.winfo_width() > 1:
            try:
                x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
                y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
                self.geometry(f"+{x}+{y}")
                return
            except:
                pass
        try:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            width = self.winfo_width()
            height = self.winfo_height()
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
            self.geometry(f"+{x}+{y}")
        except:
            pass
            
    def _on_confirm(self):
        self.result = True
        self.destroy()
        
    def _on_cancel(self):
        self.result = False
        self.destroy()

class SemanticMessageBox:
    @staticmethod
    def showinfo(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=False)
        dlg.show()
        return "ok"
        
    @staticmethod
    def showwarning(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=False)
        dlg.show()
        return "ok"
        
    @staticmethod
    def showerror(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=False)
        dlg.show()
        return "ok"
        
    @staticmethod
    def askyesno(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=True)
        return dlg.show()

    @staticmethod
    def askokcancel(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=True)
        return dlg.show()

    @staticmethod
    def askquestion(title, message, parent=None, **kwargs):
        dlg = SemanticDialog(parent, title, message, is_yesno=True)
        res = dlg.show()
        return "yes" if res else "no"

messagebox = SemanticMessageBox

import sys
import tkinter.messagebox
tkinter.messagebox.showinfo = SemanticMessageBox.showinfo
tkinter.messagebox.showwarning = SemanticMessageBox.showwarning
tkinter.messagebox.showerror = SemanticMessageBox.showerror
tkinter.messagebox.askyesno = SemanticMessageBox.askyesno
tkinter.messagebox.askokcancel = SemanticMessageBox.askokcancel
tkinter.messagebox.askquestion = SemanticMessageBox.askquestion
tkinter.messagebox = SemanticMessageBox
sys.modules['tkinter.messagebox'] = SemanticMessageBox

tkinter.messagebox.showerror = SemanticMessageBox.showerror
tkinter.messagebox.askyesno = SemanticMessageBox.askyesno
tkinter.messagebox.askokcancel = SemanticMessageBox.askokcancel
tkinter.messagebox.askquestion = SemanticMessageBox.askquestion
tkinter.messagebox = SemanticMessageBox
sys.modules['tkinter.messagebox'] = SemanticMessageBox


class ReassignProjectPICDialog(tk.Toplevel):
    def __init__(self, parent, rfq_id, customer, stage_name, current_assigned_str, bom_data_dir):
        super().__init__(parent)
        self.title("Reassign Project Stage PIC")
        self.geometry("640x560")
        self.configure(bg="#EBF8FF")
        self.transient(parent)
        self.grab_set()

        self.rfq_id = rfq_id
        self.customer = customer
        self.stage_name = stage_name
        self.current_assigned_str = current_assigned_str
        self.bom_data_dir = bom_data_dir
        self.updated = False

        # Center window
        self.update_idletasks()
        w, h = 640, 560
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.STAGE_OPTIONS = {
            "BOM Verification": "pending_bom",
            "Pending Sourcing": "pending_sourcing",
            "Pending Cycle Time": "pending_cycle_time",
            "Pending Costing": "pending_costing",
            "Pending NPI": "pending_npi",
            "Pending WI": "pending_wi",
            "All Stages": "all_stages"
        }

        clean_stage = stage_name.replace("Revert Pending -> ", "").strip()
        default_choice = clean_stage if clean_stage in self.STAGE_OPTIONS else "BOM Verification"

        hdr = tk.Frame(self, bg="#1A365D", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="👤 Reassign Project Stage PICs (Multi-User)", font=("Segoe UI", 12, "bold"), fg="white", bg="#1A365D").pack(padx=20)

        top_info = tk.Frame(self, bg="#EBF8FF", padx=20, pady=8)
        top_info.pack(fill="x")

        tk.Label(top_info, text=f"RFQ ID: {self.rfq_id}   |   Customer: {self.customer}", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D").pack(anchor="w")

        stage_sel_frame = tk.Frame(top_info, bg="#EBF8FF", pady=4)
        stage_sel_frame.pack(fill="x")
        tk.Label(stage_sel_frame, text="Select Target Stage:", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D").pack(side="left")

        self.stage_var = tk.StringVar(value=default_choice)
        self.stage_cb = ttk.Combobox(stage_sel_frame, textvariable=self.stage_var, values=list(self.STAGE_OPTIONS.keys()), state="readonly", width=25, font=("Segoe UI", 9))
        self.stage_cb.pack(side="left", padx=8)
        self.stage_cb.bind("<<ComboboxSelected>>", self._on_stage_changed)

        # Layout cols frame for TO and CC listboxes
        cols_frame = tk.Frame(self, bg="#EBF8FF", padx=15, pady=5)
        cols_frame.pack(fill="both", expand=True)
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)

        users = get_user_directory()
        self.available_users = sorted(list(users.keys()))
        if not self.available_users:
            self.available_users = ["System Administrator", "admin", "JT Tang", "ML Lim", "PH Ang", "HC Chan"]

        # COLUMN 0: TO Users
        to_f = tk.LabelFrame(cols_frame, text=" Assigned TO PICs (Action Owners) ", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D", padx=8, pady=8)
        to_f.grid(row=0, column=0, sticky="nsew", padx=5)
        to_f.rowconfigure(0, weight=1)
        to_f.columnconfigure(0, weight=1)

        self.to_listbox = tk.Listbox(to_f, font=("Segoe UI", 9), height=6, selectmode=tk.SINGLE)
        self.to_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")

        to_combo_var = tk.StringVar()
        self.to_user_cb = ttk.Combobox(to_f, textvariable=to_combo_var, values=self.available_users, state="readonly", width=16)
        self.to_user_cb.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        if self.available_users: self.to_user_cb.current(0)

        tk.Button(to_f, text="➕ Add TO", command=self._add_to_pic, bg='#3182CE', fg='white', font=("Segoe UI", 8, "bold"), relief='flat').grid(row=1, column=1, padx=4, pady=(8, 0))
        tk.Button(to_f, text="❌ Remove", command=self._remove_to_pic, bg='#E53E3E', fg='white', font=("Segoe UI", 8, "bold"), relief='flat').grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

        # COLUMN 1: CC Users
        cc_f = tk.LabelFrame(cols_frame, text=" Assigned CC Users (Keep in Loop) ", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D", padx=8, pady=8)
        cc_f.grid(row=0, column=1, sticky="nsew", padx=5)
        cc_f.rowconfigure(0, weight=1)
        cc_f.columnconfigure(0, weight=1)

        self.cc_listbox = tk.Listbox(cc_f, font=("Segoe UI", 9), height=6, selectmode=tk.SINGLE)
        self.cc_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")

        cc_combo_var = tk.StringVar()
        self.cc_user_cb = ttk.Combobox(cc_f, textvariable=cc_combo_var, values=self.available_users, state="readonly", width=16)
        self.cc_user_cb.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        if self.available_users: self.cc_user_cb.current(0)

        tk.Button(cc_f, text="➕ Add CC", command=self._add_cc_pic, bg='#3182CE', fg='white', font=("Segoe UI", 8, "bold"), relief='flat').grid(row=1, column=1, padx=4, pady=(8, 0))
        tk.Button(cc_f, text="❌ Remove", command=self._remove_cc_pic, bg='#E53E3E', fg='white', font=("Segoe UI", 8, "bold"), relief='flat').grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

        # Populate initial listboxes
        self._load_stage_pics()

        # Options check
        self.apply_all_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(self, text="Update default stage PIC & reflect to ALL projects in this stage",
                             variable=self.apply_all_var, font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#2B6CB0", activebackground="#EBF8FF")
        chk.pack(anchor="w", padx=20, pady=5)

        bot = tk.Frame(self, bg="#EBF8FF", pady=10, padx=20)
        bot.pack(fill="x", side="bottom")

        tk.Button(bot, text="Cancel", command=self.destroy, font=("Segoe UI", 9, "bold"), bg="#E2E8F0").pack(side="left")
        tk.Button(bot, text="💾 Save Assignment", command=self.on_save, font=("Segoe UI", 9, "bold"), bg="#2B6CB0", fg="white").pack(side="right")

    def _on_stage_changed(self, event=None):
        self._load_stage_pics()

    def _load_stage_pics(self):
        self.to_listbox.delete(0, tk.END)
        self.cc_listbox.delete(0, tk.END)

        stg_lbl = self.stage_var.get()
        stg_code = self.STAGE_OPTIONS.get(stg_lbl, "pending_bom")

        # First attempt to read existing RFQ file
        bom_filepath = resolve_bom_filepath(self.rfq_id, self.customer, self.bom_data_dir)
        to_users, cc_users = [], []
        if bom_filepath and os.path.exists(bom_filepath):
            try:
                with open(bom_filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                field_map = {
                    "pending_bom": "bom_assigned_by",
                    "pending_sourcing": "sourcing_assigned_by",
                    "pending_cycle_time": "cycle_time_assigned_by",
                    "pending_costing": "costing_assigned_by",
                    "pending_npi": "npi_assigned_by",
                    "pending_wi": "wi_assigned_by"
                }
                f_key = field_map.get(stg_code)
                if f_key and data.get(f_key):
                    raw_str = data.get(f_key)
                    to_users = [u.strip() for u in str(raw_str).split(",") if u.strip()]
            except Exception:
                pass

        if not to_users:
            current_pics = get_system_pics(stg_code if stg_code != "all_stages" else "pending_bom")
            to_users = current_pics.get("to", [])
            cc_users = current_pics.get("cc", [])

        for u in to_users:
            if u: self.to_listbox.insert(tk.END, u)
        for u in cc_users:
            if u: self.cc_listbox.insert(tk.END, u)

    def _add_to_pic(self):
        val = self.to_user_cb.get().strip()
        if not val: return
        existing = [self.to_listbox.get(i) for i in range(self.to_listbox.size())]
        if val in existing: return
        self.to_listbox.insert(tk.END, val)

    def _remove_to_pic(self):
        sel = self.to_listbox.curselection()
        if sel: self.to_listbox.delete(sel[0])

    def _add_cc_pic(self):
        val = self.cc_user_cb.get().strip()
        if not val: return
        existing = [self.cc_listbox.get(i) for i in range(self.cc_listbox.size())]
        if val in existing: return
        self.cc_listbox.insert(tk.END, val)

    def _remove_cc_pic(self):
        sel = self.cc_listbox.curselection()
        if sel: self.cc_listbox.delete(sel[0])

    def on_save(self):
        to_users = [self.to_listbox.get(i) for i in range(self.to_listbox.size())]
        cc_users = [self.cc_listbox.get(i) for i in range(self.cc_listbox.size())]

        if not to_users:
            messagebox.showwarning("Warning", "Please select at least one assigned TO PIC.", parent=self)
            return

        new_user_str = ", ".join(to_users)
        target_stage_lbl = self.stage_var.get()
        target_stage_code = self.STAGE_OPTIONS.get(target_stage_lbl, "pending_bom")

        bom_filepath = resolve_bom_filepath(self.rfq_id, self.customer, self.bom_data_dir)
        if not bom_filepath:
            cust_folder = self.customer.replace(" ", "_")
            bom_filepath = os.path.normpath(os.path.join(self.bom_data_dir, cust_folder, f"{self.rfq_id.replace(' ', '_')}.json"))

        top_win = self.winfo_toplevel()
        admin_name = getattr(top_win, "username", getattr(top_win, "user_name", "Admin"))

        def _update_file(fpath):
            if not fpath or not os.path.exists(fpath): return False
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if target_stage_code == "all_stages":
                    data["bom_assigned_by"] = new_user_str
                    data["bom_dispatched_by"] = new_user_str
                    data["sourcing_assigned_by"] = new_user_str
                    data["sourcing_dispatched_by"] = new_user_str
                    data["cycle_time_assigned_by"] = new_user_str
                    data["cycle_time_dispatched_by"] = new_user_str
                    data["costing_assigned_by"] = new_user_str
                    data["costing_dispatched_by"] = new_user_str
                    data["npi_assigned_by"] = new_user_str
                    data["npi_dispatched_by"] = new_user_str
                    data["wi_assigned_by"] = new_user_str
                    data["wi_dispatched_by"] = new_user_str
                    data["dispatched_by"] = new_user_str
                elif target_stage_code == "pending_bom":
                    data["bom_assigned_by"] = new_user_str
                    data["bom_dispatched_by"] = new_user_str
                elif target_stage_code == "pending_sourcing":
                    data["sourcing_assigned_by"] = new_user_str
                    data["sourcing_dispatched_by"] = new_user_str
                elif target_stage_code == "pending_cycle_time":
                    data["cycle_time_assigned_by"] = new_user_str
                    data["cycle_time_dispatched_by"] = new_user_str
                elif target_stage_code == "pending_costing":
                    data["costing_assigned_by"] = new_user_str
                    data["costing_dispatched_by"] = new_user_str
                elif target_stage_code == "pending_npi":
                    data["npi_assigned_by"] = new_user_str
                    data["npi_dispatched_by"] = new_user_str
                elif target_stage_code == "pending_wi":
                    data["wi_assigned_by"] = new_user_str
                    data["wi_dispatched_by"] = new_user_str

                current_status = data.get("status", "pending_bom")
                if current_status == target_stage_code:
                    data["dispatched_by"] = new_user_str

                hist = data.get("history", [])
                if not isinstance(hist, list): hist = []
                hist.append({
                    "Date": datetime.now().strftime("%d.%m.%Y"),
                    "Time": datetime.now().strftime("%I:%M %p"),
                    "Action": f"Stage '{target_stage_lbl}' Assigned PIC changed to '{new_user_str}' by '{admin_name}'",
                    "User": admin_name
                })
                data["history"] = hist

                with open(fpath, 'w', encoding='utf-8') as wf:
                    json.dump(data, wf, indent=4)
                return True
            except Exception as e:
                print(f"[ReassignPIC] Error updating {fpath}: {e}")
                return False

        # 1. Update selected project file
        _update_file(bom_filepath)

        # 2. Update assigned_moqs_metadata.json if present
        try:
            cust_folder = self.customer.replace(" ", "_")
            moq_meta_path = os.path.join(self.bom_data_dir, cust_folder, "assigned_moqs_metadata.json")
            if os.path.exists(moq_meta_path):
                with open(moq_meta_path, 'r', encoding='utf-8-sig') as mf:
                    mdata = json.load(mf)
                for item in mdata:
                    if item.get("rfq_id") == self.rfq_id or item.get("RFQ") == self.rfq_id:
                        item["dispatched_by"] = new_user_str
                        item["assigned_by"] = new_user_str
                with open(moq_meta_path, 'w', encoding='utf-8') as mf:
                    json.dump(mdata, mf, indent=4)
        except Exception as ex:
            print(f"[ReassignPIC] Error updating assigned_moqs_metadata: {ex}")

        # 3. Always save to system_pics.json so default stage PICs are updated
        pics_dict = {}
        stages = ["pending_bom", "pending_sourcing_and_cycle_time", "pending_sourcing", "pending_cycle_time", "pending_costing", "pending_npi", "pending_wi", "completed"]
        for stg in stages:
            pics_dict[stg] = get_system_pics(stg)

        if target_stage_code == "all_stages":
            for stg in stages:
                pics_dict[stg] = {"to": to_users, "cc": cc_users}
        else:
            pics_dict[target_stage_code] = {"to": to_users, "cc": cc_users}

        save_system_pics(pics_dict)

        # 4. If apply_all_var is True, update all project files
        if self.apply_all_var.get():
            for root, dirs, files in os.walk(self.bom_data_dir):
                for file in files:
                    if file.endswith('.json') and not file.endswith('metadata.json'):
                        fp = os.path.join(root, file)
                        _update_file(fp)

        self.updated = True
        messagebox.showinfo("Success", f"Assigned PIC for '{target_stage_lbl}' updated to '{new_user_str}' for RFQ '{self.rfq_id}'!", parent=self)
        self.destroy()

