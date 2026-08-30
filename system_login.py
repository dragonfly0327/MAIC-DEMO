import os
import json
import time
import sys
import tkinter as tk
from tkinter import ttk

# Import workflow helper from Project Management module
current_dir = os.path.dirname(os.path.abspath(__file__))
pm_dir = os.path.join(current_dir, "ref", "Project Management")
if os.path.exists(pm_dir) and pm_dir not in sys.path:
    sys.path.append(pm_dir)

try:
    from revert_workflow import get_user_directory, get_system_pics, get_user_email
except ImportError:
    # Emergency fallbacks if Project Management is not in path
    def get_user_directory(): return {}
    def get_system_pics(stage_code): return {"to": ["admin"], "cc": []}
    def get_user_email(name): return f"{str(name).strip().lower().replace(' ', '')}@continuumx.com.my" if name else ""

def verify_launcher_authorization(module_code):
    """
    Central authorization verification for ALL microservice modules.
    Verifies that:
    1. If running directly as python script (.py), allow developer access.
    2. If running as compiled (.exe), verify active launcher session token in active_session.json.
    3. The session token is fresh (not expired).
    4. The user's role has explicit permission to launch `module_code`.
    Exits process immediately with error popup if unauthorized compiled EXE execution is detected.
    """
    is_frozen = getattr(sys, 'frozen', False)
    
    # Developer Mode: If executed directly via python.exe / main.py (not compiled), allow access
    if not is_frozen:
        return {
            "username": os.environ.get("CONTXS_USER", "Developer"),
            "role": os.environ.get("CONTXS_ROLE", "Admin"),
            "email": os.environ.get("CONTXS_EMAIL", "developer@local"),
            "session_token": "DEV_BYPASS",
            "allowed_modules": [module_code.lower()],
            "timestamp": time.time()
        }

    local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))

    candidate_paths = [
        os.path.join(local_appdata, "ContXs", "active_session.json")
    ]

    session_data = None
    for s_path in candidate_paths:
        if os.path.exists(s_path):
            try:
                with open(s_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("username"):
                        session_data = data
                        break
            except Exception:
                pass

    if not session_data:
        _show_access_denied_and_exit(
            f"Access Denied: The {module_code.upper()} executable cannot be opened directly.\n\nPlease log into the ContinuumX Launcher Portal to launch this application."
        )

    # For frozen EXEs, verify that it was spawned by Launcher Portal (via env vars or CLI arguments)
    env_user = os.environ.get("CONTXS_USER")
    cli_has_user = len(sys.argv) > 1 and sys.argv[1] and not sys.argv[1].endswith(".py") and not sys.argv[1].endswith(".exe")
    
    if not env_user and not cli_has_user:
        _show_access_denied_and_exit(
            f"Access Denied: Direct execution of {module_code.upper()}.exe is prohibited.\n\nYou must open this module through the ContinuumX Launcher Portal."
        )

    # Check 1: Session Freshness (e.g. active within 24 hours)
    token_age = time.time() - session_data.get("timestamp", 0)
    if token_age > 86400:
        _show_access_denied_and_exit("Session Expired: Please log into the Launcher Portal again.")

    # Check 2: Module Permission Enforcement
    allowed_modules = [str(m).lower() for m in session_data.get("allowed_modules", [])]
    user_role = session_data.get("role", "User")
    username = session_data.get("username", "Unknown")

    if allowed_modules and user_role.lower() not in ("admin", "system administrator"):
        if module_code.lower() not in allowed_modules:
            _show_access_denied_and_exit(
                f"Access Denied: User '{username}' ({user_role}) is not authorized to access the {module_code.upper()} module."
            )

    return session_data

def _show_access_denied_and_exit(message):
    root = tk.Tk()
    root.withdraw()
    from tkinter import messagebox
    messagebox.showerror("ContinuumX Authorization Error", message)
    root.destroy()
    sys.exit(1)

def get_launcher_user_session():
    """
    Retrieves launcher logged in user details (username, role, email)
    from environment variables, sys.argv, or launcher_session.json.
    """
    env_user = os.environ.get("CONTXS_USER")
    env_role = os.environ.get("CONTXS_ROLE")
    env_email = os.environ.get("CONTXS_EMAIL")
    if env_user:
        return {
            "username": env_user,
            "role": env_role or "User",
            "email": env_email or ""
        }
        
    if len(sys.argv) > 1 and sys.argv[1] and not sys.argv[1].endswith(".py") and not sys.argv[1].endswith(".exe"):
        u = sys.argv[1]
        r = sys.argv[2] if len(sys.argv) > 2 else "User"
        e = sys.argv[3] if len(sys.argv) > 3 else ""
        return {
            "username": u,
            "role": r,
            "email": e
        }
        
    cli_has_user = len(sys.argv) > 1 and sys.argv[1] and not sys.argv[1].endswith(".py") and not sys.argv[1].endswith(".exe")

    # For frozen EXEs, if not spawned by launcher (no CONTXS_USER env and no cli user args), do NOT read background session file
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen and not env_user and not cli_has_user:
        return None

    current_dir = os.path.dirname(os.path.abspath(__file__))
    launcher_root_dir = os.path.normpath(os.path.join(current_dir, "..", ".."))
    local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
    
    session_paths = [
        os.path.join(local_appdata, "ContXs", "active_session.json")
    ]
    for s_path in session_paths:
        if os.path.exists(s_path):
            try:
                with open(s_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("username"):
                        if time.time() - data.get("timestamp", 0) < 86400:
                            return {
                                "username": data.get("username"),
                                "role": data.get("role", "User"),
                                "email": data.get("email", "")
                            }
            except Exception as e:
                print(f"[SystemLogin] Error reading session cache {s_path}: {e}")
                
    return None

def sync_user_directory_email(username, role, email):
    """Syncs user's email and role to central security vault (users.json) on login or update."""
    if not username:
        return
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            
        server_path = None
        candidate_cfgs = [
            os.path.join(current_dir, "config.ini"),
            os.path.normpath(os.path.join(current_dir, "..", "config.ini")),
            os.path.normpath(os.path.join(current_dir, "..", "..", "config.ini"))
        ]
        for cfg_path in candidate_cfgs:
            if os.path.exists(cfg_path):
                try:
                    import configparser
                    cfg = configparser.ConfigParser()
                    cfg.read(cfg_path, encoding='utf-8')
                    if 'Network' in cfg and 'ServerPath' in cfg['Network']:
                        sp = cfg['Network']['ServerPath'].strip()
                        if sp:
                            server_path = sp
                            break
                except Exception:
                    pass

        if not server_path:
            server_path = os.path.normpath(os.path.join(current_dir, "..", "ContXpps"))

        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            
        try:
            from auth_manager import AuthManager
        except ImportError:
            cur_p = current_dir
            for _ in range(3):
                cur_p = os.path.dirname(cur_p)
                if cur_p and cur_p not in sys.path:
                    sys.path.insert(0, cur_p)
                try:
                    from auth_manager import AuthManager
                    break
                except ImportError:
                    pass
            else:
                from auth_manager import AuthManager
        auth = AuthManager(server_path)
        if username in auth.users:
            changed = False
            if email and auth.users[username].get("email") != email:
                auth.users[username]["email"] = email
                changed = True
            if role and auth.users[username].get("role") != role:
                auth.users[username]["role"] = role
                changed = True
            if changed:
                auth._save_users()
    except Exception as e:
        print(f"[SyncUser] Notice: Could not sync user vault: {e}")

class SystemLoginDialog(tk.Toplevel):
    def __init__(self, master, stage_code="pending_bom", stage_name="System"):
        super().__init__(master)
        self._skip_autofit = True
        self.stage_code = stage_code
        self.stage_name = stage_name
        self.result_user = None
        self.result_role = None
        self.result_email = None
        self._force_prompt = False
        
        # Check if login details are managed by launcher
        launcher_session = get_launcher_user_session()
        if launcher_session and launcher_session.get("username"):
            username = launcher_session["username"]
            role = launcher_session.get("role", "User")
            
            # Stage Permission Authorization Check
            if username.lower() not in ("admin", "system administrator"):
                config = get_system_pics(self.stage_code)
                allowed_pics = config.get("to", []) + config.get("cc", [])
                allowed_lower = [p.lower() for p in allowed_pics]
                
                if username.lower() not in allowed_lower:
                    from tkinter import messagebox
                    messagebox.showerror(
                        "Access Denied",
                        f"Access Denied: User '{username}' ({role}) is not authorized to access {stage_name}."
                    )
                    self._unauthorized = True
                    self.result_user = None
                    self.result_role = None
                    self.result_email = None
                else:
                    self.result_user = username
                    self.result_role = role
                    self.result_email = launcher_session.get("email", "")
                    sync_user_directory_email(self.result_user, self.result_role, self.result_email)
            else:
                self.result_user = username
                self.result_role = role
                self.result_email = launcher_session.get("email", "")
                sync_user_directory_email(self.result_user, self.result_role, self.result_email)

        self.title(f"Login — {stage_name}")
        self.configure(bg="#EBF8FF")
        self.geometry("440x390")
        self.resizable(False, False)
        
        if master and master.winfo_viewable():
            try: self.transient(master)
            except: pass

        # Load Logo image safely
        self.logo_photo = None
        logo_path = None
        try:
            from config import LOGO_PATH
            logo_path = LOGO_PATH
        except ImportError:
            pass
        if not logo_path or not os.path.exists(logo_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.normpath(os.path.join(current_dir, "..", "ContinuumX Logo", "Contunuum X logo_Lettermark_Gradient (Dark).png"))

        if logo_path and os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path)
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                w = 180
                h = int(w * img.height / img.width)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading login logo: {e}")

        # Logo and Header Frame
        h_frame = tk.Frame(self, bg="#EBF8FF")
        h_frame.pack(side="top", fill="x", pady=(15, 5))
        
        if self.logo_photo:
            tk.Label(h_frame, image=self.logo_photo, bg="#EBF8FF").pack()
        else:
            tk.Label(h_frame, text="ContinuumX", font=("Segoe UI", 16, "bold"), fg="#1A365D", bg="#EBF8FF").pack()
            
        tk.Label(
            h_frame, 
            text=f"🔐 {stage_name} Access", 
            font=("Segoe UI", 12, "bold"), 
            bg="#EBF8FF", 
            fg="#1A365D"
        ).pack(pady=(5, 2))
        
        tk.Label(
            h_frame, 
            text="Please select your Username and enter password", 
            font=("Segoe UI", 9), 
            bg="#EBF8FF", 
            fg="#4A5568"
        ).pack()

        # Main Content
        content = tk.Frame(self, bg="#EBF8FF", padx=25, pady=10)
        content.pack(fill="both", expand=True)

        # Users list
        users_dir = get_user_directory()
        user_list = list(users_dir.keys())
        if "Admin" not in user_list:
            user_list.insert(0, "Admin")
            
        tk.Label(content, text="Username:", font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D").pack(anchor="w", pady=(0, 4))
        
        self.user_var = tk.StringVar()
        self.user_cb = ttk.Combobox(content, textvariable=self.user_var, values=user_list, state="readonly", font=("Segoe UI", 10))
        self.user_cb.pack(fill="x", pady=(0, 12))
        if user_list:
            self.user_cb.current(0)
            
        tk.Label(content, text="Password:", font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D").pack(anchor="w", pady=(0, 4))
        
        self.pass_entry = tk.Entry(content, show="*", font=("Segoe UI", 10), bd=1, relief="solid")
        self.pass_entry.pack(fill="x", pady=(0, 10))
        self.pass_entry.focus_set()
        
        self.err_label = tk.Label(content, text="", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#E53E3E")
        self.err_label.pack(anchor="w", pady=(0, 5))
        
        # Buttons
        btn_frame = tk.Frame(self, bg="#EBF8FF", padx=25)
        btn_frame.pack(fill="x", pady=(0, 20))
        
        cancel_btn = tk.Button(
            btn_frame, text="Cancel", command=self._on_cancel, 
            font=("Segoe UI", 10), bg="#E2E8F0", fg="#2D3748", 
            activebackground="#CBD5E0", activeforeground="#2D3748", 
            relief="flat", width=10, cursor="hand2"
        )
        cancel_btn.pack(side="left")
        
        login_btn = tk.Button(
            btn_frame, text="Login", command=self._on_login, 
            font=("Segoe UI", 10, "bold"), bg="#1A365D", fg="white", 
            activebackground="#0077B6", activeforeground="white", 
            relief="flat", width=12, cursor="hand2"
        )
        login_btn.pack(side="right")
        
        self.bind("<Return>", lambda e: self._on_login())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._center()
        self.after(100, lambda: self.pass_entry.focus_force())

    def _center(self):
        try:
            self.update_idletasks()
            if self.master and self.master.winfo_exists() and self.master.winfo_viewable():
                x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
                y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
                self.geometry(f"+{x}+{y}")
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                self.geometry(f"+{(sw - self.winfo_width()) // 2}+{(sh - self.winfo_height()) // 2}")
        except:
            pass

    def _on_login(self):
        username = self.user_var.get().strip()
        password = self.pass_entry.get().strip()
        
        # Password check (accept 'admin', '1234', or non-empty matching user)
        valid_passwords = ["admin", "1234", "radysis"]
        if password not in valid_passwords:
            self.err_label.config(text="✕ Incorrect password. Please try again.")
            self.pass_entry.delete(0, tk.END)
            return

        # Stage Permission Authorization Check
        if username.lower() not in ("admin", "system administrator"):
            config = get_system_pics(self.stage_code)
            allowed_pics = config.get("to", []) + config.get("cc", [])
            
            # Case insensitive check
            allowed_lower = [p.lower() for p in allowed_pics]
            if username.lower() not in allowed_lower:
                self.err_label.config(text=f"✕ Access Denied: '{username}' is not assigned to {self.stage_name}.")
                return

        self.result_user = username
        self.result_email = get_user_email(username)
        self.result_role = "User"
        sync_user_directory_email(self.result_user, self.result_role, self.result_email)
        self.destroy()

    def _on_cancel(self):
        self.result_user = None
        self.result_role = None
        self.result_email = None
        self.destroy()

    def show(self, force_prompt=False):
        if getattr(self, '_unauthorized', False):
            self.destroy()
            return None

        if force_prompt:
            self._force_prompt = True

        if self.result_user and not self._force_prompt:
            if self.result_user and self.result_email:
                sync_user_directory_email(self.result_user, self.result_role or "User", self.result_email or "")
            self.destroy()
            return self.result_user

        try: self.grab_set()
        except: pass
        self.wait_window()
        return self.result_user
