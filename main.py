import os
import configparser
from tkinter import messagebox
from launcher import UnifiedPortal
from auth_manager import AuthManager
from login_ui import LoginWindow, InitialSetupWindow

# ==========================================
# 3. MAIN BOOTSTRAPPER
# ==========================================
def run_portal():
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    elif len(sys.argv) > 0 and sys.argv[0]:
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        base_dir = os.getcwd()
    
    config = configparser.ConfigParser()    
    cfg_path = os.path.join(base_dir, 'config.ini')
    if not os.path.exists(cfg_path):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Configuration Error", f"Critical Error: Configuration file 'config.ini' is missing.\n\nExpected Path:\n{cfg_path}")
        root.destroy()
        sys.exit(1)

    config.read(cfg_path)
    configured = config['Network']['ServerPath'].strip()
    candidates = [
        configured,
        os.path.join(base_dir, configured),
        os.path.join(base_dir, "test_server_mock"),
    ]
    server_url = configured
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            server_url = os.path.abspath(candidate)
            break
    
    # Initialize Auth with server-side storage
    auth = AuthManager(server_url)

    def start_launcher(user_context):
        app = UnifiedPortal(server_url, user_context, on_logout=show_login)
        app.mainloop()

    def start_app(user_context):
        if user_context['role'] == "Pending":
            messagebox.showwarning("Access Denied", "Your account is currently PENDING approval. Please wait for an Admin to assign your role.")
            show_login()
            return

        admin_roles = {"admin", "administrator", "system administrator", "top management"}
        is_admin_user = user_context.get('username', '').lower() in ("admin", "sysadmin")
        is_admin_role = str(user_context.get('role', '')).lower() in admin_roles

        if is_admin_user or is_admin_role:
            from admin_ui import AdminDashboard
            app = AdminDashboard(auth, user_context, start_launcher, on_logout=show_login)
            app.mainloop()
        else:
            start_launcher(user_context)

    def show_login():
        login = LoginWindow(auth, start_app)
        login.mainloop()

    # Flow Control
    if not auth.has_users():
        # First time setup: Create Admin
        setup = InitialSetupWindow(auth, show_login)
        setup.mainloop()
    else:
        # Standard Login
        show_login()

if __name__ == "__main__":
    run_portal()