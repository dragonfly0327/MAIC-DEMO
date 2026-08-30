import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

class AdminDashboard(tk.Tk):
    def __init__(self, auth_manager, current_user, on_launch_portal, on_logout=None):
        super().__init__()
        self.auth = auth_manager
        self.user = current_user
        self.on_launch_portal = on_launch_portal
        self.on_logout = on_logout
        
        self.title("ContinuumX - Management Console")
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 1060, 640
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(980, 580)
        self.configure(bg="#f8f9fa")
        
        # Set Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "images", "logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        self.main_container = tk.Frame(self, bg="#f8f9fa")
        self.main_container.pack(fill="both", expand=True)
        
        # Global Bindings
        self.bind("<Escape>", lambda e: self._on_esc_pressed())

        # Router State
        self.current_username_to_edit = ""
        self.temp_settings = None # For system settings steps
        
        self.show_list_view()

    def clear_view(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    # ==========================================
    # USER LIST VIEW
    # ==========================================
    def show_list_view(self):
        self.clear_view()
        self.title("Management Console - User List")
        self.unbind("<Return>") # Reset return for list
        self.bind("<Return>", lambda e: self.go_to_edit())
        
        # Header
        header = tk.Frame(self.main_container, bg="#2c3e50", height=80)
        header.pack(fill="x")
        tk.Label(header, text="Console", font=("Arial", 18, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=20)
        
        info = tk.Frame(header, bg="#2c3e50")
        info.pack(side="right", padx=20)
        tk.Label(info, text=f"Admin: {self.user['username']}", bg="#2c3e50", fg="#bdc3c7", font=("Arial", 9)).pack(anchor="e")
        tk.Button(info, text="Logout", bg="#e74c3c", fg="white", font=("Arial", 8), command=self.logout).pack(anchor="e", pady=2)

        body = tk.Frame(self.main_container, bg="#f8f9fa", padx=30, pady=20)
        body.pack(fill="both", expand=True)

        # Toolbar
        toolbar = tk.Frame(body, bg="#f8f9fa")
        toolbar.pack(fill="x", pady=(0, 15))
        tk.Label(toolbar, text="Global User Registry", font=("Arial", 12, "bold"), bg="#f8f9fa").pack(side="left")

        # Table
        table_frame = tk.Frame(body, bg="white", highlightbackground="#dee2e6", highlightthickness=1)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(table_frame, columns=("username", "role"), show="headings", selectmode="browse")
        self.tree.heading("username", text="Username")
        self.tree.heading("role", text="Role / Department")
        self.tree.column("username", width=300); self.tree.column("role", width=300)
        
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Actions Panel
        actions = tk.Frame(body, bg="#f8f9fa", pady=20)
        actions.pack(fill="x")

        tk.Button(actions, text="+ New User", bg="#27ae60", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.show_add_view).pack(side="left", padx=5)
        
        tk.Button(actions, text="⚙️ Edit Account", bg="#f39c12", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.go_to_edit).pack(side="left", padx=5)
        
        tk.Button(actions, text="🗑 Delete", bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.on_delete).pack(side="left", padx=5)

        tk.Button(actions, text="🛡 System Config", bg="#34495e", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.show_settings_view).pack(side="left", padx=5)

        tk.Button(actions, text="🔐 Role Permissions", bg="#8e44ad", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.show_permissions_view).pack(side="left", padx=5)

        tk.Button(actions, text="Launch Feature Portal ➜", bg="#3498db", fg="white", font=("Arial", 9, "bold"), 
                  padx=15, command=self.launch_portal).pack(side="right")

        self.refresh_user_list()

    def refresh_user_list(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        users = self.auth.get_all_users()
        self.tree.tag_configure("pending",  background="#fff3cd")
        self.tree.tag_configure("sysadmin", background="#d5e8d4", foreground="#2d6a2d")  # Green for SA
        
        my_rank = self.auth.ROLE_RANK.get(self.user['role'], 0)
        for u in users:
            target_rank = self.auth.ROLE_RANK.get(u['role'], 0)
            # Only show users this editor outranks (or themselves)
            if target_rank > my_rank:
                continue
            if u['role'] == "Pending":
                tags = ("pending",)
            elif u['role'] == "System Administrator":
                tags = ("sysadmin",)
            else:
                tags = ()
            self.tree.insert("", "end", values=(u['username'], u['role']), tags=tags)

    def go_to_edit(self):
        sel = self.tree.selection()
        if not sel: return messagebox.showwarning("Selection", "Please select a user.")
        self.show_edit_view(self.tree.item(sel[0])['values'][0])

    # ==========================================
    # EDIT USER VIEW
    # ==========================================
    def show_edit_view(self, username, is_new=False):
        self.clear_view()
        self.title(f"Editing: {username}")

        # --- Permission check before rendering ---
        my_role     = self.user['role']
        target_data = self.auth.users.get(username, {})
        target_role = target_data.get('role', 'Pending')
        is_peer_tm  = self.auth.is_peer_top_management_edit(my_role, target_role) and not is_new
        
        header = tk.Frame(self.main_container, bg="#f39c12" if not is_new else "#27ae60", height=60)
        header.pack(fill="x")
        tk.Label(header, text="User Management" if not is_new else "Create User",
                 font=("Arial", 14, "bold"), bg=header['bg'], fg="white").pack(pady=15)

        body = tk.Frame(self.main_container, bg="#f8f9fa", padx=50, pady=20)
        body.pack(fill="both")

        tk.Button(body, text="← Back to List", relief="flat", command=self.show_list_view).pack(anchor="w", pady=(0, 15))

        # Peer TM banner
        if is_peer_tm:
            banner = tk.Frame(body, bg="#e8f4fd", pady=10)
            banner.pack(fill="x", pady=(0, 10))
            tk.Label(banner, text="⚠️  Editing another Top Management account — 2FA from target required",
                     bg="#e8f4fd", fg="#2980b9", font=("Arial", 9, "bold")).pack()

        tk.Label(body, text=f"Target: {username}", font=("Arial", 12, "bold")).pack(anchor="w", pady=(5, 10))

        user_data = target_data

        # Email
        tk.Label(body, text="Email Address").pack(anchor="w")
        e_entry = ttk.Entry(body); e_entry.pack(fill="x", pady=5)
        e_entry.insert(0, user_data.get('email', ''))

        # Role — only show roles the editor can assign
        my_rank = self.auth.ROLE_RANK.get(my_role, 0)
        assignable = [r for r in self.auth.ROLES if self.auth.ROLE_RANK.get(r, 0) < my_rank]
        tk.Label(body, text="Department Role").pack(anchor="w", pady=(10, 0))
        r_var = tk.StringVar(value=user_data.get('role', 'Pending'))
        r_menu = ttk.Combobox(body, textvariable=r_var, values=assignable, state="readonly")
        r_menu.pack(fill="x", pady=5)

        # Password
        label_p = "Set Password" if is_new else "Reset Password (Leave blank for no change)"
        tk.Label(body, text=label_p).pack(anchor="w", pady=(10, 0))
        p_entry = ttk.Entry(body, show="●"); p_entry.pack(fill="x", pady=5)

        # Peer TM 2FA panel
        target_code_entry = None
        if is_peer_tm:
            tfa_frame = tk.LabelFrame(body, text="Target User 2FA Verification", padx=20, pady=12, bg="#eaf4fb")
            tfa_frame.pack(fill="x", pady=(15, 5))
            tk.Label(tfa_frame, text=f"Send a verification code to {username}'s email first:",
                     bg="#eaf4fb", font=("Arial", 9)).pack(anchor="w")
            send_btn = tk.Button(tfa_frame, text="📧 Send Code to Target",
                                 bg="#3498db", fg="white", relief="flat",
                                 command=lambda: self._send_target_2fa(username, send_btn))
            send_btn.pack(anchor="w", pady=5)
            tk.Label(tfa_frame, text="Enter code received by target user:", bg="#eaf4fb", font=("Arial", 9)).pack(anchor="w")
            target_code_entry = ttk.Entry(tfa_frame, justify="center", font=("Arial", 11))
            target_code_entry.pack(fill="x", pady=5)

        # Admin authorization
        auth_frame = tk.LabelFrame(body, text="Administrator Authorization", padx=20, pady=12, bg="#ecf0f1")
        auth_frame.pack(fill="x", pady=15)
        tk.Label(auth_frame, text="Confirm your Admin Password to save changes:", bg="#ecf0f1", font=("Arial", 9)).pack()
        admin_p = ttk.Entry(auth_frame, show="●", justify="center"); admin_p.pack(fill="x", pady=5)

        def save(event=None):
            pwd = admin_p.get()
            if not pwd: return messagebox.showwarning("Auth", "Admin password required.")

            t2fa = target_code_entry.get().strip() if target_code_entry else None

            if is_new:
                if not p_entry.get(): return messagebox.showwarning("Input", "Password required for new user.")
                success, msg = self.auth.register_user(username, p_entry.get(), r_var.get(), e_entry.get())
            else:
                success, msg = self.auth.update_user_full(
                    username, self.user['username'], pwd,
                    e_entry.get(), r_var.get(), p_entry.get(),
                    target_2fa_code=t2fa
                )

            if success:
                messagebox.showinfo("Success", msg)
                self.show_list_view()
            else:
                messagebox.showerror("Error", msg)

        self.bind("<Return>", save)
        tk.Button(body, text="SAVE & CONFIRM" if not is_new else "CREATE USER",
                  bg="#2c3e50", fg="white", font=("Arial", 10, "bold"), pady=10, command=save).pack(fill="x")

    def show_add_view(self):
        # We need to prompt for username first
        dialog = tk.Toplevel(self)
        dialog.title("Identify User")
        dialog.geometry("300x150")
        tk.Label(dialog, text="Enter username for new user:").pack(pady=10)
        u_entry = ttk.Entry(dialog); u_entry.pack(pady=5)
        u_entry.focus_set()
        
        def next():
            u = u_entry.get().strip()
            if not u: return
            dialog.destroy()
            self.show_edit_view(u, is_new=True)
            
        tk.Button(dialog, text="Continue", command=next).pack(pady=10)

    def _send_target_2fa(self, target_username, btn):
        """Send a 2FA verification code to the TARGET user's email (for peer TM→TM edits)."""
        btn.config(state="disabled", text="📧 Sending...")
        self.update_idletasks()

        def bg_send():
            success, msg = self.auth.send_target_verification(target_username)
            def post_send():
                btn.config(state="normal", text="📧 Send Code to Target")
                if success:
                    messagebox.showinfo("Code Sent", f"A 6-digit code has been sent to {target_username}'s registered email.\nAsk them to share it with you to proceed.")
                else:
                    messagebox.showerror("Send Failed", msg)
            self.after(0, post_send)

        import threading
        threading.Thread(target=bg_send, daemon=True).start()

    # ==========================================
    # SYSTEM SETTINGS VIEW
    # ==========================================
    def show_settings_view(self, step=1):
        self.clear_view()
        self.title("Global System Configuration")
        
        header = tk.Frame(self.main_container, bg="#34495e", height=60)
        header.pack(fill="x")
        tk.Label(header, text="System & Email Settings", font=("Arial", 14, "bold"), bg="#34495e", fg="white").pack(pady=15)

        body = tk.Frame(self.main_container, bg="#f8f9fa", padx=50, pady=30)
        body.pack(fill="both")

        tk.Button(body, text="← Back to List", relief="flat", command=self.show_list_view).pack(anchor="w", pady=(0, 20))

        if step == 1: # Input
            self._render_settings_input(body)
        elif step == 2: # Verify
            self._render_settings_verify(body)

    def _render_settings_input(self, body):
        tk.Label(body, text="System Configuration", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 20))
        
        can_edit_sys = (self.user['username'] == "sysadmin")
        
        if can_edit_sys:
            tk.Label(body, text="Central Mailing Credentials", font=("Arial", 9, "bold")).pack(anchor="w", pady=(10, 0))

            tk.Label(body, text="SMTP Server (e.g. mail.domain.com or smtp.gmail.com)").pack(anchor="w")
            sv = ttk.Entry(body); sv.pack(fill="x", pady=5)
            sv.insert(0, self.auth.system_settings.get("smtp_server", "smtp.gmail.com"))

            tk.Label(body, text="SMTP Port  (465 = SSL  |  587 = STARTTLS)").pack(anchor="w", pady=(5, 0))
            sp = ttk.Entry(body); sp.pack(fill="x", pady=5)
            sp.insert(0, str(self.auth.system_settings.get("smtp_port", 465)))

            tk.Label(body, text="System Email Address").pack(anchor="w", pady=(5, 0))
            u = ttk.Entry(body); u.pack(fill="x", pady=5)
            u.insert(0, self.auth.system_settings.get("email_user", ""))

            tk.Label(body, text="Email Password / App Password").pack(anchor="w", pady=(5, 0))
            p = ttk.Entry(body, show="●"); p.pack(fill="x", pady=5)
        else:
            u  = tk.StringVar(value=self.auth.system_settings.get("email_user", ""))
            p  = tk.StringVar(value="")
            sv = tk.StringVar(value=self.auth.system_settings.get("smtp_server", ""))
            sp = tk.StringVar(value=str(self.auth.system_settings.get("smtp_port", 465)))

        tk.Label(body, text="Application Settings", font=("Arial", 9, "bold")).pack(anchor="w", pady=(20, 0))
        tk.Label(body, text="Fallback Company Email").pack(anchor="w", pady=(5, 0))
        f = ttk.Entry(body); f.pack(fill="x", pady=5)
        f.insert(0, self.auth.system_settings.get("fallback_email", ""))

        def verify():
            email_val  = u.get()
            pass_val   = p.get()
            server_val = sv.get()
            port_val   = sp.get()
            self.temp_settings = (email_val, pass_val, f.get(), server_val, port_val)

            if not can_edit_sys:
                self.show_settings_view(step=2)
                return

            success, msg = self.auth.send_new_system_verify_email(
                email_val, pass_val, f.get(), server_val, port_val
            )
            if success:
                messagebox.showinfo("Sent", msg)
                self.show_settings_view(step=2)
            else:
                messagebox.showerror("Error", msg)

        tk.Button(body, text="CONTINUE TO SAVE" if not can_edit_sys else "VERIFY & CONTINUE",
                  bg="#3498db", fg="white", font=("Arial", 10, "bold"), pady=10, command=verify).pack(fill="x", pady=30)
        self.bind("<Return>", lambda e: verify())

    def _render_settings_verify(self, body):
        can_edit_sys = (self.user['username'] == "sysadmin")
        
        if can_edit_sys:
            tk.Label(body, text=f"Verification code sent to {self.temp_settings[0]}", font=("Arial", 10)).pack(pady=10)
            c_entry = ttk.Entry(body, font=("Arial", 12), justify="center"); c_entry.pack(fill="x", pady=5)
            
            def check_code():
                return self.auth.validate_system_code(self.temp_settings[0], c_entry.get().strip(), "_system_new_verify_")
        else:
            tk.Label(body, text="Review Changes", font=("Arial", 12, "bold")).pack(pady=10)
            tk.Label(body, text=f"New Fallback Email: {self.temp_settings[2]}").pack(pady=5)
            def check_code(): return True # No code needed for fallback-only non-sysadmin

        # Inline Auth Panel
        auth_frame = tk.LabelFrame(body, text="Final Authorization", padx=20, pady=15, bg="#ecf0f1")
        auth_frame.pack(fill="x", pady=20)
        tk.Label(auth_frame, text="Enter Admin Password to confirm changes:", bg="#ecf0f1").pack()
        admin_p = ttk.Entry(auth_frame, show="●", justify="center"); admin_p.pack(fill="x", pady=5)

        def finalize():
            ap = admin_p.get()
            if not ap: return messagebox.showwarning("Auth", "Admin password required.")
            
            # 1. Verify Admin Password
            admin_data = self.auth.users.get(self.user['username'])
            if not self.auth.verify_password(admin_data['hash'], ap):
                return messagebox.showerror("Auth", "Incorrect Admin Password.")

            # 2. Verify Code (if sysadmin)
            if not check_code():
                return messagebox.showerror("Error", "Invalid verification code.")

            # 3. Save
            final_email  = self.temp_settings[0] if can_edit_sys else self.auth.system_settings.get("email_user")
            final_pass   = self.temp_settings[1] if can_edit_sys else self.auth.decrypt_secret(self.auth.system_settings.get("email_pass"))
            final_server = self.temp_settings[3] if can_edit_sys and len(self.temp_settings) > 3 else self.auth.system_settings.get("smtp_server", "smtp.gmail.com")
            final_port   = self.temp_settings[4] if can_edit_sys and len(self.temp_settings) > 4 else self.auth.system_settings.get("smtp_port", 465)

            self.auth.update_system_settings(final_email, final_pass, self.temp_settings[2], final_server, str(final_port))
            messagebox.showinfo("Success", "Global settings updated!")
            self.show_list_view()

        tk.Button(body, text="CONFIRM & SAVE SETTINGS", bg="#27ae60", fg="white", 
                        font=("Arial", 10, "bold"), pady=10, command=finalize).pack(fill="x", pady=10)
        
        if can_edit_sys:
            tk.Button(body, text="Resend Code", relief="flat", command=lambda: self.auth.send_new_system_verify_email(*self.temp_settings)).pack()
        
        self.bind("<Return>", lambda e: finalize())

    # ==========================================
    # ROLE MODULE PERMISSIONS VIEW
    # ==========================================
    def show_permissions_view(self):
        self.clear_view()
        self.title("Role-Module Access Control Configuration")
        
        header = tk.Frame(self.main_container, bg="#8e44ad", height=60)
        header.pack(fill="x")
        tk.Label(header, text="Role & Feature Access Control", font=("Arial", 14, "bold"), bg="#8e44ad", fg="white").pack(pady=15)

        body = tk.Frame(self.main_container, bg="#f8f9fa", padx=30, pady=20)
        body.pack(fill="both", expand=True)

        tk.Button(body, text="← Back to List", relief="flat", command=self.show_list_view).pack(anchor="w", pady=(0, 10))

        tk.Label(body, text="Select Role to Configure Authorized Features:", font=("Arial", 10, "bold"), bg="#f8f9fa").pack(anchor="w", pady=(0, 5))
        
        all_roles = [r for r in self.auth.ROLES if r != "System Administrator"]
        role_var = tk.StringVar(value=all_roles[0] if all_roles else "Engineering")
        
        # Role selection strip + Add New Role button
        role_strip = tk.Frame(body, bg="#f8f9fa")
        role_strip.pack(fill="x", pady=5)

        role_combo = ttk.Combobox(role_strip, textvariable=role_var, values=all_roles, state="readonly", font=("Arial", 10))
        role_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))

        def on_add_new_role():
            dlg = tk.Toplevel(self)
            dlg.title("Create New Role")
            dlg.geometry("360x180")
            dlg.configure(bg="#f8f9fa")
            dlg.grab_set()

            tk.Label(dlg, text="New Role Name:", font=("Arial", 10, "bold"), bg="#f8f9fa").pack(anchor="w", padx=20, pady=(15, 5))
            r_entry = ttk.Entry(dlg, font=("Arial", 10))
            r_entry.pack(fill="x", padx=20, pady=(0, 15))
            r_entry.focus_set()

            def submit_new_role():
                new_r = r_entry.get().strip()
                if not new_r:
                    return messagebox.showwarning("Input Error", "Please enter a role name.", parent=dlg)
                success, msg = self.auth.add_custom_role(new_r)
                if success:
                    messagebox.showinfo("Role Created", msg, parent=dlg)
                    dlg.destroy()
                    updated_roles = [r for r in self.auth.ROLES if r != "System Administrator"]
                    role_combo['values'] = updated_roles
                    role_var.set(new_r)
                    load_role_checkboxes()
                else:
                    messagebox.showerror("Error", msg, parent=dlg)

            btn_frame = tk.Frame(dlg, bg="#f8f9fa")
            btn_frame.pack(fill="x", padx=20)
            tk.Button(btn_frame, text="Cancel", command=dlg.destroy, bg="#cbd5e1", fg="#1e293b", relief="flat", width=10).pack(side="left")
            tk.Button(btn_frame, text="+ Create", command=submit_new_role, bg="#27ae60", fg="white", font=("Arial", 9, "bold"), relief="flat", width=12).pack(side="right")
            dlg.bind("<Return>", lambda e: submit_new_role())

        add_role_btn = tk.Button(role_strip, text="➕ Add New Role", bg="#27ae60", fg="white", font=("Arial", 9, "bold"), padx=10, command=on_add_new_role, relief="flat", cursor="hand2")
        add_role_btn.pack(side="right")

        all_modules = ["BOM", "Sourcing", "Cycle Time", "Costing", "NPI", "WI", "Project Management"]
        cb_vars = {}

        card_frame = tk.LabelFrame(body, text="Authorized Modules", bg="white", padx=20, pady=15)
        card_frame.pack(fill="both", expand=True, pady=15)

        def load_role_checkboxes(*args):
            for child in card_frame.winfo_children():
                child.destroy()
            selected_role = role_var.get()
            allowed = self.auth.get_role_permissions(selected_role)
            allowed_lower = [m.lower() for m in allowed]
            cb_vars.clear()

            for mod in all_modules:
                var = tk.BooleanVar(value=(mod.lower() in allowed_lower))
                cb_vars[mod] = var
                cb = tk.Checkbutton(card_frame, text=f"  {mod} Module", variable=var,
                                    font=("Arial", 10, "bold" if var.get() else "normal"),
                                    bg="white", anchor="w", activebackground="white")
                cb.pack(fill="x", pady=4)

        role_combo.bind("<<ComboboxSelected>>", load_role_checkboxes)
        load_role_checkboxes()

        def save_permissions():
            selected_role = role_var.get()
            selected_mods = [mod for mod, var in cb_vars.items() if var.get()]
            success, msg = self.auth.update_role_permissions(selected_role, selected_mods)
            if success:
                messagebox.showinfo("Success", msg)
            else:
                messagebox.showerror("Error", msg)

        tk.Button(body, text="SAVE PERMISSIONS", bg="#8e44ad", fg="white", font=("Arial", 10, "bold"), pady=10, command=save_permissions).pack(fill="x")
    def on_delete(self):
        sel = self.tree.selection()
        if not sel: return
        user = self.tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Delete {user}?"):
            self.verify_admin_action(lambda p: self._finalize_delete(user, p))

    def _finalize_delete(self, user, pwd):
        if not pwd:
            return False, "Admin password is required."
        success, msg = self.auth.delete_user(user, self.user['username'], requester_password=pwd)
        if success:
            messagebox.showinfo("Deleted", msg)
            self.refresh_user_list()
            return True, ""
        return False, msg

    def verify_admin_action(self, callback):
        win = tk.Toplevel(self)
        win.title("Authorize")
        win.geometry("300x150")
        tk.Label(win, text="Confirm Admin Password").pack(pady=10)
        e = ttk.Entry(win, show="●"); e.pack(pady=5); e.focus_set()
        def sub():
            s, m = callback(e.get())
            if s: win.destroy()
            else: messagebox.showerror("Error", m)
        tk.Button(win, text="Confirm", command=sub).pack(pady=10)
        win.bind("<Return>", lambda e: sub())
        win.bind("<Escape>", lambda e: win.destroy())

    def _on_esc_pressed(self):
        # Determine current view and act like a back button
        title = self.title()
        if "Editing" in title or "System Configuration" in title or "Create User" in title:
            self.show_list_view()

    def launch_portal(self):
        self.destroy()
        self.on_launch_portal(self.user)

    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.destroy()
            if self.on_logout:
                self.on_logout()
            else:
                import sys
                os.execl(sys.executable, sys.executable, *sys.argv)
