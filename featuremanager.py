import os
import sys
import json
import shutil
import zipfile
import psutil
import subprocess
from tkinter import messagebox

# ==========================================
# 2. FEATURE LOGIC MODULE
# ==========================================
class FeatureManager:
    def __init__(self, key, server_path):
        self.key = key
        self.server_path = server_path
        self.local_base = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), "ContinuumX")
        self.feature_dir = os.path.join(self.local_base, "features", key)
        self.icon_cache = os.path.join(self.local_base, "cache", "icons")
        self.manifest_path = os.path.join(self.feature_dir, "local_manifest.json")

        os.makedirs(self.icon_cache, exist_ok=True)
        os.makedirs(self.local_base, exist_ok=True)

    def local_source_path(self):
        """repo ref/<Module>/main.py used when no downloaded .exe is present."""
        repo_root = os.path.dirname(os.path.abspath(__file__))
        ref_py_map = {
            "BOM": os.path.join(repo_root, "ref", "BOM", "main.py"),
            "Sourcing": os.path.join(repo_root, "ref", "Sourcing", "main.py"),
            "Cycle Time": os.path.join(repo_root, "ref", "Cycle Time", "main.py"),
            "Costing": os.path.join(repo_root, "ref", "Costing", "main.py"),
            "NPI": os.path.join(repo_root, "ref", "NPI", "main.py"),
            "WI": os.path.join(repo_root, "ref", "WI", "main.py"),
            "Project Management": os.path.join(repo_root, "ref", "Project Management", "main.py"),
        }
        path = ref_py_map.get(self.key)
        return path if path and os.path.exists(path) else None

    def get_local_version(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, 'r') as f:
                return json.load(f).get("version")
        return None

    def sync_icon(self, icon_name):
        if not icon_name: return None
        
        # Define a local cache folder for icons
        icon_cache = os.path.join(self.local_base, "cache", "icons")
        os.makedirs(icon_cache, exist_ok=True)
        
        local_path = os.path.join(icon_cache, icon_name)
        remote_path = os.path.join(self.server_path, "binaries", icon_name)
        
        # Copy from server if not already local
        if not os.path.exists(local_path) and os.path.exists(remote_path):
            try:
                shutil.copy2(remote_path, local_path)
            except Exception as e:
                print(f"Error syncing icon: {e}")
                return None
                
        return local_path

    def is_running(self):
        # Check if already running
        try:
            for p in psutil.process_iter(['name']):
                if p.info['name'] == f"{self.key}.exe":
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        return False

    def perform_sync(self, remote_info, update_fn):
        if self.is_running():
            return False, f"Please close {self.key} first."

        try:
            zip_src = os.path.join(self.server_path, "binaries", remote_info['file'])
            if not os.path.exists(zip_src):
                return False, f"Binary file not found on server [ERR_SYNC_001]. Expected path: {zip_src}"

            temp_id = f"extract_{remote_info['file'].replace('.', '_')}"
            temp_dir = os.path.join(self.local_base, "temp", temp_id)
            
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            update_fn("Extracting...", 60)
            with zipfile.ZipFile(zip_src, 'r') as z:
                z.extractall(temp_dir)

            update_fn("Finalizing...", 90)
            # Use atomic replacement if possible, but shutil.rmtree + shutil.move is standard for directories
            if os.path.exists(self.feature_dir): 
                shutil.rmtree(self.feature_dir)
            shutil.move(temp_dir, self.feature_dir)
            
            with open(self.manifest_path, 'w') as f:
                json.dump(remote_info, f)
            return True, "Success"
        except Exception as e:
            return False, f"[ERR_SYNC_003] Failed during extraction/move: {str(e)}"

    def open_manual(self, manual_name):
        if not manual_name:
            return
        
        # Path to the manual on the server
        remote_manual_path = os.path.join(self.server_path, "manuals", manual_name)
        
        if os.path.exists(remote_manual_path):
            try:
                os.startfile(remote_manual_path)
            except Exception as e:
                print(f"Failed to open manual: {e}")
        else:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Not Found", f"User manual not found on server:\n{manual_name}")

    def launch(self, user_context=None):
        target_folder = os.path.join(self.feature_dir, self.key)
        exe_path = os.path.join(target_folder, f"{self.key}.exe")
        
        # Check source mode fallback (ref/<Module>/main.py)
        ref_py_path = self.local_source_path()
        if (not os.path.exists(exe_path) or not getattr(sys, "frozen", False)) and ref_py_path:
            exe_path = ref_py_path
            target_folder = os.path.dirname(ref_py_path)
            is_py_mode = True
        else:
            is_py_mode = False

        # Dynamic search if default location/name doesn't match
        if not is_py_mode and not os.path.exists(exe_path):
            exe_candidates = []
            search_dirs = [target_folder, self.feature_dir]
            for s_dir in search_dirs:
                if os.path.exists(s_dir):
                    for f in os.listdir(s_dir):
                        if f.lower().endswith(".exe"):
                            exe_candidates.append(os.path.join(s_dir, f))
            if exe_candidates:
                exe_path = exe_candidates[0]
                target_folder = os.path.dirname(exe_path)
            else:
                exe_path = os.path.join(self.feature_dir, f"{self.key}.exe")
                target_folder = self.feature_dir

        if os.path.exists(exe_path):
            try:
                # Clean environment dictionary to prevent frozen Python encodings import error
                env = os.environ.copy()
                for key in ["PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE", "PYTHONWEXECUTABLE", "_MEIPASS", "VIRTUAL_ENV"]:
                    env.pop(key, None)
                cmd = [sys.executable, exe_path] if is_py_mode or exe_path.endswith(".py") else [exe_path]
                if user_context and isinstance(user_context, dict):
                    username = user_context.get("username", "")
                    role = user_context.get("role", "")
                    email = user_context.get("email", "")
                    
                    env["CONTXS_USER"] = username
                    env["CONTXS_ROLE"] = role
                    env["CONTXS_EMAIL"] = email
                    if self.server_path:
                        env["CONTXS_SERVER_PATH"] = self.server_path

                    cmd.extend([username, role, email])

                    # Cache active session in %LOCALAPPDATA%/ContXs and temp for token authorization
                    import time, uuid
                    from auth_manager import AuthManager
                    
                    auth = AuthManager(self.server_path)
                    allowed_modules = auth.get_role_permissions(role)

                    session_payload = {
                        "username": username,
                        "role": role,
                        "email": email,
                        "server_path": self.server_path,
                        "session_token": str(uuid.uuid4()),
                        "allowed_modules": allowed_modules,
                        "timestamp": time.time()
                    }
                    try:
                        feature_dir = os.path.dirname(os.path.abspath(__file__))
                        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
                        session_paths = [
                            os.path.join(local_appdata, "ContXs", "active_session.json"),
                            os.path.join(feature_dir, "launcher_session.json"),
                            os.path.join(os.environ.get('TEMP', os.environ.get('TMP', 'C:\\Temp')), "contxs_launcher_session.json")
                        ]
                        for s_path in session_paths:
                            os.makedirs(os.path.dirname(s_path), exist_ok=True)
                            with open(s_path, 'w', encoding='utf-8') as sf:
                                json.dump(session_payload, sf, indent=4)
                    except Exception as e:
                        print(f"Warning: Could not save launcher session cache: {e}")

                # CRITICAL: cwd must be the folder containing the .exe 
                # so the standalone app can find its .dll and .pyd files.
                subprocess.Popen(cmd, cwd=target_folder, env=env)
            except Exception as e:
                messagebox.showerror("Execution Error", f"Failed to start process:\n{str(e)}")
        else:
            messagebox.showerror("Error", 
                f"Executable not found.\nExpected path:\n{exe_path}")