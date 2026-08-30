from tkinter import Toplevel, Frame, Label, Button, filedialog
import os
from datetime import date, datetime
import time, json

class SemanticDialog(Toplevel):
    def __init__(self, master, title, message, is_yesno=False):
        import tkinter as tk
        
        # Flush the event queue to ensure any previous window destruction/grab release is fully processed
        if master:
            try: master.update_idletasks()
            except: pass
            
        # Fallback to the active visible big window if master is None or default root
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
                        # Sort by area (width * height) descending to get the largest viewable window (main active big window)
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
        
        # Determine theme based on title
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
        
        # Header
        header_frame = Frame(self, bg=colors["header_bg"], bd=1, relief="solid")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        header_label = Label(header_frame, text=t, font=("Segoe UI", 11, "bold"), bg=colors["header_bg"], fg=colors["header_fg"])
        header_label.pack(pady=8)
        
        # Content Area
        content_frame = Frame(self, bg="#EBF8FF", bd=0)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Message
        msg_label = Label(content_frame, text=message, font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D", justify="left", wraplength=350)
        msg_label.pack(padx=20, pady=20)
        
        # Buttons
        btn_frame = Frame(self, bg="#EBF8FF")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        # Determine button text
        confirm_text = "Proceed" if is_yesno else "OK"
        if self.theme == "error": confirm_text = "Close"
        if "SELECTION" in t: confirm_text = "Understood"
        
        # Cancel Button (ALWAYS Bottom-Left)
        self.cancel_btn = None
        if is_yesno:
            cancel_btn = Button(btn_frame, text="Cancel", command=self._on_cancel, width=10, bg="#E2E8F0", fg="#2D3748", font=("Segoe UI", 10), activebackground="#CBD5E0", activeforeground="#2D3748", relief="flat", bd=0, cursor="hand2")
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(bg="#CBD5E0", fg="#2D3748"))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(bg="#E2E8F0", fg="#2D3748"))
            cancel_btn.bind("<FocusIn>", lambda e: cancel_btn.configure(bg="#CBD5E0", fg="#2D3748"))
            cancel_btn.bind("<FocusOut>", lambda e: cancel_btn.configure(bg="#E2E8F0", fg="#2D3748"))
            cancel_btn.bind("<Return>", lambda e: self._on_cancel_event(e))
            cancel_btn.pack(side="left")
            self.cancel_btn = cancel_btn
            
        # Confirm Button (ALWAYS Bottom-Right)
        confirm_btn = Button(btn_frame, text=confirm_text, command=self._on_confirm, width=10, bg=colors["btn_bg"], fg="white", font=("Segoe UI", 10, "bold"), activebackground="#0077B6" if colors["btn_bg"] == "#1A365D" else "#c82333", relief="flat", bd=0, cursor="hand2")
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
        
        self.withdraw()  # Hide dialog to prevent screen flicker during centering
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
        
        # Fallback: perfect centering on the system screen
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

# Define base project directory (supporting PyInstaller and Nuitka compiled paths)
import sys
if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.getcwd()

import configparser

# Load configuration with multi-tier path resolution fallback
config = configparser.ConfigParser()
config_candidates = [
    os.path.join(BASE_DIR, "config.ini"),
    os.path.normpath(os.path.join(BASE_DIR, "..", "config.ini")),
    os.path.normpath(os.path.join(BASE_DIR, "..", "..", "config.ini")),
    os.path.normpath(os.path.join(os.path.dirname(sys.executable), "config.ini")),
    os.path.normpath(os.path.join(os.path.dirname(sys.executable), "..", "config.ini")),
    os.path.normpath(os.path.join(os.path.dirname(sys.executable), "..", "..", "config.ini"))
]

config_file = next((p for p in config_candidates if os.path.exists(p)), None)
if config_file:
    try:
        config.read(config_file, encoding='utf-8')
    except Exception as e:
        print(f"Error reading config file ({config_file}): {e}")

CONFIG = config  # Alias export for compatibility

# Resolve base directory (SERVER_PATH)
SERVER_PATH = BASE_DIR
if config.has_option('PATHS', 'SERVER_PATH'):
    val = config.get('PATHS', 'SERVER_PATH').strip()
    if val:
        val = val.replace('\\', '/')
        if os.path.isabs(val) or val.startswith('//') or val.startswith('\\\\'):
            SERVER_PATH = os.path.normpath(val)
        else:
            base_ref = os.path.dirname(config_file) if config_file else BASE_DIR
            SERVER_PATH = os.path.normpath(os.path.join(base_ref, val))

def get_config_path(default_rel_path):
    """
    Returns the path resolved relative to the SERVER_PATH base directory.
    """
    return os.path.normpath(os.path.join(SERVER_PATH, default_rel_path))

def load_server_path():
    """Returns the central server base directory loaded dynamically from environment, session cache, or config.ini."""
    # 1. Check environment variable (passed by Central Launcher)
    env_sp = os.environ.get("CONTXS_SERVER_PATH")
    if env_sp and env_sp.strip():
        return env_sp.strip()

    # 2. Check active session cache saved by Central Launcher
    try:
        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
        session_file = os.path.join(local_appdata, "ContXs", "active_session.json")
        if os.path.exists(session_file):
            import json
            with open(session_file, 'r', encoding='utf-8') as sf:
                sdata = json.load(sf)
                sp = sdata.get("server_path")
                if sp and sp.strip():
                    return sp.strip()
    except Exception:
        pass

    # 3. Search candidate config.ini files
    b_dir = BASE_DIR
    programdata_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
    candidate_cfgs = [
        os.path.join(b_dir, "config.ini"),
        os.path.normpath(os.path.join(b_dir, "..", "config.ini")),
        os.path.normpath(os.path.join(b_dir, "..", "..", "config.ini")),
        os.path.normpath(os.path.join(b_dir, "..", "..", "..", "config.ini")),
        os.path.join(programdata_dir, "ContinuumX", "config.ini")
    ]
    for cfg_path in candidate_cfgs:
        if os.path.exists(cfg_path):
            try:
                import configparser
                cfg = configparser.ConfigParser()
                cfg.read(cfg_path, encoding='utf-8')
                if 'Network' in cfg and 'ServerPath' in cfg['Network']:
                    sp = cfg['Network']['ServerPath'].strip()
                    if sp: return sp
                if 'PATHS' in cfg and 'server_path' in cfg['PATHS']:
                    sp = cfg['PATHS']['server_path'].strip()
                    if sp: return sp
            except Exception:
                pass
    return os.path.normpath(os.path.join(b_dir, "..", "..", "test_server_mock"))

def get_logo_path(logo_type="LOGO_PROFILE_DARK"):
    """
    Returns the absolute path to logo image, searching config.ini options first,
    then SERVER_PATH, _MEIPASS, BASE_DIR, sys.executable dirs, and parent directories.
    """
    candidates = []
    
    # 1. Config specified paths
    try:
        opts = [logo_type, logo_type.lower()] if logo_type else []
        for opt in ['LOGO_PROFILE_DARK', 'LOGO_PATH', 'logo_profile_dark', 'logo_path', 'LOGO_HORIZONTAL_DARK', 'LOGO_PROFILE_LIGHT', 'LOGO_HORIZONTAL_LIGHT']:
            if opt not in opts: opts.append(opt)

        for opt in opts:
            if config.has_option('PATHS', opt):
                p = config.get('PATHS', opt).strip()
                if p:
                    p = p.replace('\\', '/')
                    if os.path.isabs(p) or p.startswith('//') or p.startswith('\\\\'):
                        candidates.append(os.path.normpath(p))
                    else:
                        base_ref = os.path.dirname(config_file) if config_file else BASE_DIR
                        candidates.append(os.path.normpath(os.path.join(base_ref, p)))
    except Exception:
        pass

    sp = load_server_path()
    if sp:
        candidates.append(os.path.join(sp, "assets", "logo_profile_dark.png"))
        candidates.append(os.path.join(sp, "assets", "images", "logo_profile_dark.png"))

    if logo_type and "HORIZONTAL" in str(logo_type).upper():
        logo_names = [
            "logo_horizontal_dark.png",
            "logo_horizontal_light.png",
            "logo_profile_dark.png",
            "logo_profile_light.png",
            "logo.png"
        ]
    else:
        logo_names = [
            "logo_profile_dark.png",
            "Contunuum X logo_Lettermark_Gradient (Dark).png",
            "logo_profile_light.png",
            "logo_horizontal_dark.png",
            "logo.png",
            "ContinuumX.png",
            "ContinuumX.ico"
        ]
    
    subdirs = ["assets", "assets/images", "ContinuumX Logo", ""]

    base_dirs = []
    if BASE_DIR:
        base_dirs.append(BASE_DIR)
        base_dirs.append(os.path.normpath(os.path.join(BASE_DIR, "..")))
        base_dirs.append(os.path.normpath(os.path.join(BASE_DIR, "..", "..")))
    if SERVER_PATH and os.path.exists(SERVER_PATH):
        base_dirs.append(SERVER_PATH)
    if hasattr(sys, '_MEIPASS'):
        base_dirs.append(sys._MEIPASS)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        base_dirs.append(exe_dir)
        base_dirs.append(os.path.normpath(os.path.join(exe_dir, "..")))
        base_dirs.append(os.path.normpath(os.path.join(exe_dir, "..", "..")))

    for name in logo_names:
        for b in base_dirs:
            for sub in subdirs:
                p = os.path.normpath(os.path.join(b, sub, name)) if sub else os.path.normpath(os.path.join(b, name))
                candidates.append(p)

    for p in candidates:
        if p and os.path.exists(p):
            return p

    if SERVER_PATH and os.path.exists(os.path.join(SERVER_PATH, "assets")):
        assets_dir = os.path.join(SERVER_PATH, "assets")
        for root_dir, _, files in os.walk(assets_dir):
            for fname in files:
                if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico')):
                    if 'logo_profile' in fname.lower() or 'logo' in fname.lower() or 'continuum' in fname.lower():
                        return os.path.join(root_dir, fname)

    return os.path.join(BASE_DIR, "ContinuumX.ico")

# Data Paths (Relative to SERVER_PATH)
DATA_PATH = get_config_path(os.path.join("Excel Files", "MPN_Master_Data.xlsx"))
excel_folder = get_config_path("Excel Files")
macro_file = os.path.join(excel_folder, "macro_RFQBOM.xlsm")
log_folder = get_config_path("logfile")

# Master Data Paths
MASTER_DATA_DIR = get_config_path("Master Data")
EXCHANGE_RATE_FILE = os.path.join(MASTER_DATA_DIR, "Exchange Rate.json")
MARKUP_RATE_FILE = os.path.join(MASTER_DATA_DIR, "Markup Rate.json")
CURRENCY_CONFIG_FILE = os.path.join(MASTER_DATA_DIR, "Currency Config.json")

# New Data Storage Directories
SYNTHETIC_BOM_DIR = get_config_path("Synthetic BOM")
BOM_DATA_DIR = get_config_path("BOM Data")
SOURCING_DIR = os.path.join(MASTER_DATA_DIR, "Sourcing")
INDIVIDUAL_BOM_DATA_DIR = get_config_path("Individual BOM Data")
ALT_MPN_DIR = get_config_path("Customer Parts - Alternative MPNs")
TEMP_DIR = get_config_path("Temp")

# Ensure directories exist
for d in [MASTER_DATA_DIR, log_folder, os.path.dirname(DATA_PATH), SYNTHETIC_BOM_DIR, BOM_DATA_DIR, SOURCING_DIR, INDIVIDUAL_BOM_DATA_DIR, ALT_MPN_DIR, TEMP_DIR]:
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as ex:
            print(f"[Warning] Could not create directory {d}: {ex}")

# Standard headers for the Sourcing sheet
SOURCING_HEADER = [
    "Source Date", "Description", "Supplier", "MFR", "MPN", 
    "Currency", "UOM", "Std Pack", "Stock", "L/Time (weeks)", 
    "Shipping Terms", "Remark (Attachment)", "Unit Price", "Supplier Quote",
    "Unit Price Validity Duration (Days)", "Unit Price Validity",
    "Stock Duration (Days)", "Stock Validity", "Status"
]

# Config for BOM Formatter
STANDARD_COLUMNS = [
    'Assy #',
    'Assy Model',
    'Assy Rev',
    'Part',
    'Description',
    'MFR',
    'MPN',
    'Qty',
    'UOM',
    'Line Item'
]

MANDATORY_COLUMNS = ['Assy #', 'Assy Model', 'Assy Rev', 'Part', 'Description', 'MFR', 'MPN', 'Qty', 'UOM', 'Line Item']
SPECIAL_SELECTION_COLUMNS = ['Assy #', 'Assy Model', 'Assy Rev'] 
MULTI_SOURCE_COLUMNS = ['MFR', 'MPN']

# File types for dialogs
EXCEL_FILETYPES = [("Excel files", "*.xlsx *.xls")]

def show_info(title, message, parent=None):
    if parent:
        messagebox.showinfo(title, message, parent=parent)
    else:
        messagebox.showinfo(title, message)

def show_error(title, message, parent=None):
    if parent:
        messagebox.showerror(title, message, parent=parent)
    else:
        messagebox.showerror(title, message)

def get_next_sequence_number(sheet):
    """Returns the next sequence number based on the number of rows."""
    return str(sheet.max_row)

def get_current_date_sequence():
    """Returns the current date as a string."""
    return str(date.today())

def ask_excel_file_paths(parent_root):
    file_paths = filedialog.askopenfilenames(
        parent=parent_root,
        title="Select one or more files to be processed",
        filetypes=[("Excel files", "*.xlsx *.xls *.xlsm")]
    )
    return file_paths

def change_file_extension(file_path, new_extension):
    root, _ = os.path.splitext(file_path)
    new_path = root + new_extension
    return new_path

def ask_save_file_path(parent_root):
    save_path = filedialog.asksaveasfilename(
        parent=parent_root,
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx")],
        title="Save Processed Data As"
    )
    return save_path

def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"File '{file_path}' deleted successfully.")
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except PermissionError:
        print(f"Error: You do not have permission to delete '{file_path}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_log_file(excel_path):
    keyword_to_trim = "_BOM"
    log_keyword = "_bom-log.txt"

    if keyword_to_trim in excel_path:
        filename = os.path.basename(excel_path)
        basename = filename.split(keyword_to_trim)[0]

        log_file_name = f"{basename}{log_keyword}"
        log_path = os.path.join(log_folder, log_file_name)
        return log_path
    else: 
        print(f"'{keyword_to_trim}' not found in the file path.")
        return None

class Logger:
    def __init__(self, filename: str):
        self.filename = filename
        self._initialize_log_file()

    def _initialize_log_file(self):
        initial_string = "BOM Verified By: "
        dir_name = os.path.dirname(self.filename)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as file:
                file.write(f"{initial_string}\n")

    def record_text(self, text: str, append_timestamp: bool = True):
        with open(self.filename, 'a') as file:
            if append_timestamp:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file.write(f"[{timestamp}] {text}\n")
            else:
                file.write(f"{text}\n")

def merge_mpn_mfr_pairs(existing_mpn, existing_mfr, db_mpn, db_mfr):
    ext_mpns = [m.strip() for m in str(existing_mpn).split(",") if m.strip()]
    ext_mfrs = [m.strip() for m in str(existing_mfr).split(",") if m.strip()]
    while len(ext_mfrs) < len(ext_mpns): ext_mfrs.append("")
    while len(ext_mpns) < len(ext_mfrs): ext_mpns.append("")
    
    db_mpns = [m.strip() for m in str(db_mpn).split(",") if m.strip()]
    db_mfrs = [m.strip() for m in str(db_mfr).split(",") if m.strip()]
    while len(db_mfrs) < len(db_mpns): db_mfrs.append("")
    while len(db_mpns) < len(db_mfrs): db_mpns.append("")
    
    seen = set()
    merged_pairs = []
    
    for mpn, mfr in zip(ext_mpns, ext_mfrs):
        key = (mpn.upper(), mfr.upper())
        if key not in seen:
            seen.add(key)
            merged_pairs.append((mpn, mfr))
            
    for mpn, mfr in zip(db_mpns, db_mfrs):
        key = (mpn.upper(), mfr.upper())
        if key not in seen:
            seen.add(key)
            merged_pairs.append((mpn, mfr))
            
    final_mpns = ", ".join([p[0] for p in merged_pairs])
    final_mfrs = ", ".join([p[1] for p in merged_pairs])
    return final_mpns, final_mfrs

def get_alternative_mpn_path(cust_name):
    safe_cust = cust_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    alt_mpn_dir = ALT_MPN_DIR
    cust_dir = os.path.join(alt_mpn_dir, safe_cust)
    new_path = os.path.join(cust_dir, "Alternative_MPNs.json")
    
    legacy_path = os.path.join(alt_mpn_dir, f"{safe_cust}.json")
    
    if os.path.exists(legacy_path) and not os.path.exists(new_path):
        try:
            if not os.path.exists(cust_dir):
                os.makedirs(cust_dir)
            import shutil
            shutil.copy2(legacy_path, new_path)
            print(f"Migrated legacy alternative MPNs file from {legacy_path} to {new_path}")
        except Exception as e:
            print(f"Error migrating legacy alternative MPNs file: {e}")
            
    if not os.path.exists(cust_dir):
        os.makedirs(cust_dir)
        
    return new_path

def acquire_session_lock(rfq_id, username):
    """
    Attempts to acquire a session lock for the given RFQ.
    Returns (True, None) if lock is successfully acquired.
    Returns (False, locked_by_user) if another user holds the lock.
    """
    import json
    # Use SERVER_PATH to resolve Locks folder
    locks_dir = os.path.normpath(os.path.join(os.path.dirname(SERVER_PATH), "Locks"))
    if not os.path.exists(locks_dir):
        try:
            os.makedirs(locks_dir)
        except:
            return True, None # Fail-safe
            
    lock_file = os.path.join(locks_dir, f"RFQ_{rfq_id.replace(' ', '_')}.lock")
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                lock_data = json.load(f)
            locked_by = lock_data.get("user", "Unknown")
            lock_time = lock_data.get("timestamp", 0)
            
            # Check for stale lock (4 hours)
            if time.time() - lock_time > 14400:
                os.remove(lock_file)
            elif locked_by != username:
                return False, locked_by
        except:
            pass
            
    try:
        with open(lock_file, "w") as f:
            json.dump({"user": username, "timestamp": time.time()}, f)
        return True, None
    except:
        return True, None # Fail-safe

def release_session_lock(rfq_id, username):
    """Releases the session lock for the given RFQ."""
    locks_dir = os.path.normpath(os.path.join(os.path.dirname(SERVER_PATH), "Locks"))
    lock_file = os.path.join(locks_dir, f"RFQ_{rfq_id.replace(' ', '_')}.lock")
    if os.path.exists(lock_file):
        try:
            import json
            with open(lock_file, "r") as f:
                lock_data = json.load(f)
            if lock_data.get("user") == username:
                os.remove(lock_file)
        except:
            try:
                os.remove(lock_file)
            except:
                pass

def load_uom_conversions():
    import json
    path = get_config_path("uom_conversions.json")
    default_data = {
        "tolerance_pct": 5.0,
        "rules": {
            "FT": {"to_uom": "M", "factor": 0.3048, "apply_tolerance": True},
            "IN": {"to_uom": "M", "factor": 0.0254, "apply_tolerance": True},
            "MM": {"to_uom": "M", "factor": 0.001, "apply_tolerance": True},
            "EA": {"to_uom": "EA", "factor": 1.0, "apply_tolerance": False}
        }
    }
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "tolerance_pct" in data and "rules" in data:
                    return data
        except:
            pass
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=4)
    except:
        pass
    return default_data

def save_uom_conversions(data):
    import json
    path = get_config_path("uom_conversions.json")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True
    except:
        return False

def check_rfq_exists(rfq_id, cust_name=None):
    """
    Checks if an RFQ number already exists anywhere in the system across all customers.
    Returns the existing Customer Name string if found, or None if not found.
    """
    if not rfq_id:
        return None
    norm_rfq = str(rfq_id).strip()
    if not norm_rfq:
        return None
        
    safe_rfq = norm_rfq.replace(" ", "_")
    norm_rfq_lower = norm_rfq.lower()
    safe_rfq_lower = safe_rfq.lower()

    # 1. Search BOM_DATA_DIR across ALL customer subfolders
    if os.path.exists(BOM_DATA_DIR):
        for root, dirs, files in os.walk(BOM_DATA_DIR):
            for file in files:
                if file.endswith(".json") and not file.endswith("metadata.json"):
                    fname_no_ext = file[:-5]
                    filepath = os.path.join(root, file)
                    j_cust = None
                    j_rfq = None
                    try:
                        with open(filepath, 'r', encoding='utf-8') as jf:
                            jdata = json.load(jf)
                            j_cust = str(jdata.get("Customer", "")).strip()
                            j_rfq = str(jdata.get("RFQ", "")).strip()
                    except Exception:
                        pass

                    folder_cust = os.path.basename(root)
                    found_cust = j_cust or folder_cust or "Existing Customer"

                    if fname_no_ext.lower() in (safe_rfq_lower, norm_rfq_lower):
                        return found_cust
                    if j_rfq and j_rfq.lower() == norm_rfq_lower:
                        return found_cust

    # 2. Check in INDIVIDUAL_BOM_DATA_DIR across all folders
    if os.path.exists(INDIVIDUAL_BOM_DATA_DIR):
        for root, dirs, files in os.walk(INDIVIDUAL_BOM_DATA_DIR):
            for file in files:
                if file.endswith(".json") and not file.endswith("metadata.json"):
                    fname_no_ext = file[:-5]
                    filepath = os.path.join(root, file)
                    j_cust = None
                    j_rfq = None
                    try:
                        with open(filepath, 'r', encoding='utf-8') as jf:
                            jdata = json.load(jf)
                            j_cust = str(jdata.get("Customer", "")).strip()
                            j_rfq = str(jdata.get("RFQ", "")).strip()
                    except Exception:
                        pass

                    folder_cust = os.path.basename(root)
                    found_cust = j_cust or folder_cust or "Existing Customer"

                    if fname_no_ext.lower() in (safe_rfq_lower, norm_rfq_lower):
                        return found_cust
                    if j_rfq and j_rfq.lower() == norm_rfq_lower:
                        return found_cust

    return None

def get_bom_creation_date(raw_data, filepath=None):
    """
    Extracts or resolves the initial BOM creation timestamp formatted as dd.mm.yyyy (HH:MM AM/PM).
    Falls back gracefully to history log, timestamp field, or file creation/mod time.
    """
    from datetime import datetime

    def format_dt(dt_obj):
        return dt_obj.strftime("%d.%m.%Y (%I:%M %p)")

    if isinstance(raw_data, dict):
        # 1. Direct field
        c_at = raw_data.get("created_at") or raw_data.get("bom_creation_date")
        if c_at and str(c_at).strip():
            c_str = str(c_at).strip()
            for fmt in ("%Y-%m-%d %I:%M %p", "%d.%m.%Y (%I:%M %p)", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %I:%M %p", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
                try:
                    dt_obj = datetime.strptime(c_str, fmt)
                    return format_dt(dt_obj)
                except ValueError:
                    pass
            return c_str
            
        # 2. Check history (first log entry = initial creation)
        history = raw_data.get("history", [])
        if history and isinstance(history, list) and len(history) > 0:
            first_h = history[0]
            if isinstance(first_h, dict):
                h_date = first_h.get("Date", "").strip()
                h_time = first_h.get("Time", "").strip()
                if h_date:
                    if h_time:
                        dt_str = f"{h_date} {h_time}"
                        for fmt in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %I:%M:%S %p", "%Y-%m-%d %I:%M:%S %p", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M"):
                            try:
                                dt_obj = datetime.strptime(dt_str, fmt)
                                return format_dt(dt_obj)
                            except ValueError:
                                pass
                        return f"{h_date} ({h_time})"
                    return h_date

        # 3. Check Timestamp field
        ts = raw_data.get("Timestamp") or raw_data.get("timestamp") or raw_data.get("Date")
        if ts and str(ts).strip():
            ts_str = str(ts).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %I:%M %p", "%d.%m.%Y %I:%M %p", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    dt_obj = datetime.strptime(ts_str, fmt)
                    return format_dt(dt_obj)
                except ValueError:
                    pass
            return ts_str

    # 4. Fallback to file modification time if filepath provided
    if filepath and os.path.exists(filepath):
        try:
            mtime = os.path.getmtime(filepath)
            return format_dt(datetime.fromtimestamp(mtime))
        except Exception:
            pass

    # 5. Default current time if no record exists
    return format_dt(datetime.now())


def atomic_write_json(filepath, data):
    """
    Writes data to a temporary file in the same directory and renames it to filepath.
    Guarantees atomic updates on Windows and POSIX without data corruption.
    """
    import os, json
    dir_name = os.path.dirname(filepath)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    temp_filepath = filepath + ".tmp"
    with open(temp_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(temp_filepath, filepath)

