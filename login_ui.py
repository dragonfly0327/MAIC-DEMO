import tkinter as tk
from tkinter import ttk, messagebox
import os

class LoginWindow(tk.Tk):
    def __init__(self, auth_manager, on_success):
        super().__init__()
        self.auth = auth_manager
        self.on_success = on_success
        
        self.title("ContinuumX Launcher - Secure Login")
        self.geometry("400x600")
        self.resizable(False, False)
        self.configure(bg="#f3f6f9")
        
        # Set Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "images", "logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        # Router State
        self.view_container = tk.Frame(self, bg="#f3f6f9")
        self.view_container.pack(fill="both", expand=True)
        
        # Recovery State
        self.recovery_step = 1
        self.recovery_user = ""
        
        self.show_login_view()

    def clear_view(self):
        for widget in self.view_container.winfo_children():
            widget.destroy()

    # ==========================================
    # LOGIN VIEW
    # ==========================================
    def show_login_view(self):
        self.clear_view()
        self.title("ContinuumX - Login")
        
        header = tk.Frame(self.view_container, bg="#2c3e50", height=120)
        header.pack(fill="x")
        tk.Label(header, text="ContinuumX", font=("Arial", 22, "bold"), bg="#2c3e50", fg="#ecf0f1").pack(pady=(30, 0))
        tk.Label(header, text="SECURE ACCESS PORTAL", font=("Arial", 8), bg="#2c3e50", fg="#bdc3c7").pack()

        body = tk.Frame(self.view_container, bg="#f3f6f9", padx=40, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Username", font=("Arial", 10), bg="#f3f6f9", fg="#34495e").pack(anchor="w")
        self.user_entry = ttk.Entry(body, font=("Arial", 11))
        self.user_entry.pack(fill="x", pady=(5, 15))
        self.user_entry.focus_set()

        tk.Label(body, text="Password", font=("Arial", 10), bg="#f3f6f9", fg="#34495e").pack(anchor="w")
        self.pass_entry = ttk.Entry(body, show="●", font=("Arial", 11))
        self.pass_entry.pack(fill="x", pady=(5, 20))
        self.pass_entry.bind('<Return>', lambda e: self.attempt_login())

        login_btn = tk.Button(body, text="LOGIN", command=self.attempt_login, 
                            bg="#3498db", fg="white", font=("Arial", 10, "bold"), 
                            cursor="hand2", relief="flat", padx=20, pady=10)
        login_btn.pack(fill="x")

        # Links
        links_frame = tk.Frame(body, bg="#f3f6f9")
        links_frame.pack(pady=20)
        
        forgot_btn = tk.Label(links_frame, text="Forgot Password?", font=("Arial", 9, "underline"), 
                             bg="#f3f6f9", fg="#34495e", cursor="hand2")
        forgot_btn.pack()
        forgot_btn.bind("<Button-1>", lambda e: self.show_recovery_view(1))

        tk.Label(body, text="Don't have an account?", font=("Arial", 9), bg="#f3f6f9").pack(pady=(10, 0))
        reg_btn = tk.Label(body, text="Register Now", font=("Arial", 9, "bold"), 
                          bg="#f3f6f9", fg="#27ae60", cursor="hand2")
        reg_btn.pack()
        reg_btn.bind("<Button-1>", lambda e: self.show_register_view())

        self.bind("<Return>", lambda e: self.attempt_login())
        self.bind("<Escape>", lambda e: self.destroy())

        # Footer
        footer = tk.Label(self.view_container, text="© 2026 Continuum Xolutions PLT", 
                        font=("Arial", 8), bg="#f3f6f9", fg="#95a5a6")
        footer.pack(side="bottom", pady=20)

    def attempt_login(self):
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get()
        
        if not user or not pwd:
            messagebox.showwarning("Input Required", "Please enter both username and password.")
            return

        user_context, msg = self.auth.verify_login(user, pwd)
        if user_context:
            self.destroy()
            self.on_success(user_context)
        else:
            messagebox.showerror("Login Failed", msg)
            self.pass_entry.delete(0, tk.END)

    # ==========================================
    # REGISTRATION VIEW
    # ==========================================
    def show_register_view(self):
        self.clear_view()
        self.title("ContinuumX - Registration")
        self.bind("<Escape>", lambda e: self.show_login_view())

        header = tk.Frame(self.view_container, bg="#27ae60", height=80)
        header.pack(fill="x")
        tk.Label(header, text="Self-Registration", font=("Arial", 14, "bold"), bg="#27ae60", fg="white").pack(pady=25)

        body = tk.Frame(self.view_container, bg="#f3f6f9", padx=40, pady=20)
        body.pack(fill="both", expand=True)

        tk.Button(body, text="← Back to Login", relief="flat", bg="#f3f6f9", fg="#7f8c8d", 
                  font=("Arial", 9), command=self.show_login_view).pack(anchor="w", pady=(0, 20))

        # Inputs
        tk.Label(body, text="Username", bg="#f3f6f9", font=("Arial", 9)).pack(anchor="w")
        u_entry = ttk.Entry(body); u_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Email", bg="#f3f6f9", font=("Arial", 9)).pack(anchor="w")
        e_entry = ttk.Entry(body); e_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Password", bg="#f3f6f9", font=("Arial", 9)).pack(anchor="w")
        p_entry = ttk.Entry(body, show="●"); p_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Confirm Password", bg="#f3f6f9", font=("Arial", 9)).pack(anchor="w")
        c_entry = ttk.Entry(body, show="●"); c_entry.pack(fill="x", pady=5)

        def submit(event=None):
            u, e, p, c = u_entry.get().strip(), e_entry.get().strip(), p_entry.get(), c_entry.get()
            if not u or not e or not p:
                messagebox.showwarning("Error", "All fields are required.")
                return
            if p != c:
                messagebox.showerror("Mismatch", "Passwords do not match.")
                return
            
            success, msg = self.auth.register_self(u, p, e)
            if success:
                messagebox.showinfo("Success", msg)
                self.show_login_view()
            else:
                messagebox.showerror("Error", msg)

        tk.Button(body, text="SUBMIT REGISTRATION", bg="#27ae60", fg="white", 
                        font=("Arial", 10, "bold"), pady=10, command=submit).pack(fill="x", pady=25)
        self.bind("<Return>", submit)
        self.bind("<Escape>", lambda e: self.show_login_view())

    # ==========================================
    # RECOVERY VIEW
    # ==========================================
    def show_recovery_view(self, step):
        self.clear_view()
        self.title("ContinuumX - Recovery")

        header = tk.Frame(self.view_container, bg="#e67e22", height=80)
        header.pack(fill="x")
        tk.Label(header, text="Password Recovery", font=("Arial", 14, "bold"), bg="#e67e22", fg="white").pack(pady=25)

        body = tk.Frame(self.view_container, bg="#f3f6f9", padx=40, pady=20)
        body.pack(fill="both", expand=True)

        if step == 1:
            self._render_recovery_s1(body)
        elif step == 2:
            self._render_recovery_s2(body)
        elif step == 3:
            self._render_recovery_s3(body)

    def _render_recovery_s1(self, body):
        tk.Button(body, text="← Back to Login", relief="flat", bg="#f3f6f9", fg="#7f8c8d", 
                  command=self.show_login_view).pack(anchor="w", pady=(0, 20))
        
        tk.Label(body, text="Enter username to receive 2FA code:", bg="#f3f6f9").pack(anchor="w")
        u_entry = ttk.Entry(body); u_entry.pack(fill="x", pady=5)

        def send():
            user = u_entry.get().strip()
            if not user: return
            
            # Disable button and show sending status
            send_btn.config(state="disabled", text="SENDING...")
            self.update_idletasks()

            def bg_send():
                success, msg = self.auth.send_verification_email(user)
                
                def post_send():
                    try:
                        if send_btn.winfo_exists():
                            send_btn.config(state="normal", text="SEND CODE")
                    except Exception:
                        pass
                    if success:
                        self.recovery_user = user
                        self.show_recovery_view(2)
                    else:
                        messagebox.showerror("Error", msg)
                
                try:
                    self.after(0, post_send)
                except Exception:
                    pass

            import threading
            threading.Thread(target=bg_send, daemon=True).start()

        send_btn = tk.Button(body, text="SEND CODE", bg="#3498db", fg="white", font=("Arial", 10, "bold"), 
                  pady=8, command=send)
        send_btn.pack(fill="x", pady=15)
        self.bind("<Return>", lambda e: send())
        self.bind("<Escape>", lambda e: self.show_login_view())

    def _render_recovery_s2(self, body):
        tk.Label(body, text=f"Identify code sent to email of '{self.recovery_user}'", 
                 font=("Arial", 9), bg="#f3f6f9", wraplength=300).pack(pady=10)
        
        code_entry = ttk.Entry(body, font=("Arial", 11), justify="center"); code_entry.pack(fill="x", pady=5)

        def verify():
            if self.auth.validate_code(self.recovery_user, code_entry.get().strip()):
                self.show_recovery_view(3)
            else:
                messagebox.showerror("Invalid Code", "Incorrect or expired code.")

        tk.Button(body, text="VERIFY CODE", bg="#27ae60", fg="white", font=("Arial", 10, "bold"), 
                  pady=8, command=verify).pack(fill="x", pady=10)
        self.bind("<Return>", lambda e: verify())
        self.bind("<Escape>", lambda e: self.show_recovery_view(1))
        
        def resend():
            resend_btn.config(state="disabled", text="Resending...")
            def bg_resend():
                success, msg = self.auth.send_verification_email(self.recovery_user)
                def post_resend():
                    try:
                        if resend_btn.winfo_exists():
                            resend_btn.config(state="normal", text="Resend Code")
                    except Exception:
                        pass
                    if success:
                        messagebox.showinfo("Sent", "A new code has been sent.")
                    else:
                        messagebox.showerror("Error", msg)
                try:
                    self.after(0, post_resend)
                except Exception:
                    pass
            
            import threading
            threading.Thread(target=bg_resend, daemon=True).start()

        resend_btn = tk.Button(body, text="Resend Code", bg="#f3f6f9", fg="#3498db", relief="flat", 
                  command=resend)
        resend_btn.pack()

        tk.Button(body, text="← Back", relief="flat", bg="#f3f6f9", fg="#7f8c8d", 
                  command=lambda: self.show_recovery_view(1)).pack(pady=10)

    def _render_recovery_s3(self, body):
        tk.Label(body, text="Enter your new password", bg="#f3f6f9").pack(anchor="w")
        p1 = ttk.Entry(body, show="●"); p1.pack(fill="x", pady=5)
        tk.Label(body, text="Confirm password", bg="#f3f6f9").pack(anchor="w", pady=(10, 0))
        p2 = ttk.Entry(body, show="●"); p2.pack(fill="x", pady=5)

        def finalize():
            if p1.get() != p2.get():
                messagebox.showerror("Error", "Passwords do not match.")
                return
            # Note: auth logic uses stored code internally.
            code, _ = self.auth.active_codes.get(self.recovery_user)
            success, msg = self.auth.reset_password(self.recovery_user, p1.get(), code)
            if success:
                messagebox.showinfo("Success", "Password changed!")
                self.show_login_view()
            else:
                messagebox.showerror("Error", msg)

        tk.Button(body, text="UPDATE PASSWORD", bg="#f39c12", fg="white", font=("Arial", 10, "bold"), 
                  pady=10, command=finalize).pack(fill="x", pady=20)
        self.bind("<Return>", lambda e: finalize())
        self.bind("<Escape>", lambda e: self.show_recovery_view(2))


class InitialSetupWindow(tk.Tk):
    def __init__(self, auth_manager, on_complete):
        super().__init__()
        self.auth = auth_manager
        self.on_complete = on_complete
        
        self.title("ContinuumX - First Time Setup")
        self.geometry("450x700")
        self.resizable(False, False)
        self.configure(bg="#f3f6f9")

        # Set Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "images", "logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        self.bind("<Return>", lambda e: self.create_account())

        self.setup_ui()

    def setup_ui(self):
        header = tk.Frame(self, bg="#2c3e50", height=80)
        header.pack(fill="x")
        tk.Label(header, text="SYSTEM INITIALIZATION", font=("Arial", 14, "bold"), bg="#2c3e50", fg="white").pack(pady=25)

        canvas = tk.Canvas(self, borderwidth=0, background="#f3f6f9")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, background="#f3f6f9", padx=40, pady=20)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        body = scrollable_frame

        tk.Label(body, text="Admin Account Details", font=("Arial", 10, "bold"), bg="#f3f6f9").pack(anchor="w")
        
        tk.Label(body, text="Admin Username", bg="#f3f6f9").pack(anchor="w")
        self.user_entry = ttk.Entry(body, font=("Arial", 11)); self.user_entry.pack(fill="x", pady=5)
        self.user_entry.insert(0, "sysadmin")

        tk.Label(body, text="Admin Password", bg="#f3f6f9").pack(anchor="w")
        self.pass_entry = ttk.Entry(body, show="●", font=("Arial", 11)); self.pass_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Confirm Password", bg="#f3f6f9").pack(anchor="w")
        self.conf_entry = ttk.Entry(body, show="●", font=("Arial", 11)); self.conf_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Personal Email (for your 2FA)", bg="#f3f6f9").pack(anchor="w")
        self.email_entry = ttk.Entry(body, font=("Arial", 11)); self.email_entry.pack(fill="x", pady=5)

        # --- SYSTEM EMAIL SECTION ---
        tk.Frame(body, height=2, bg="#bdc3c7").pack(fill="x", pady=15)
        tk.Label(body, text="Central System Email Setup", font=("Arial", 10, "bold"), bg="#f3f6f9").pack(anchor="w")
        tk.Label(body, text="(Used by the system to send all 2FA codes)", font=("Arial", 8, "italic"), bg="#f3f6f9", fg="#7f8c8d").pack(anchor="w")

        tk.Label(body, text="SMTP Server  (e.g. mail.company.com  or  smtp.gmail.com)", bg="#f3f6f9").pack(anchor="w")
        self.smtp_serv_entry = ttk.Entry(body, font=("Arial", 11)); self.smtp_serv_entry.pack(fill="x", pady=5)
        self.smtp_serv_entry.insert(0, "smtp.gmail.com")

        tk.Label(body, text="SMTP Port  (465 for SSL  |  587 for STARTTLS)", bg="#f3f6f9").pack(anchor="w")
        self.smtp_port_entry = ttk.Entry(body, font=("Arial", 11)); self.smtp_port_entry.pack(fill="x", pady=5)
        self.smtp_port_entry.insert(0, "465")

        tk.Label(body, text="System Email Address", bg="#f3f6f9").pack(anchor="w")
        self.sys_email_entry = ttk.Entry(body, font=("Arial", 11)); self.sys_email_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Email Password / App Password", bg="#f3f6f9").pack(anchor="w")
        self.sys_pass_entry = ttk.Entry(body, show="●", font=("Arial", 11)); self.sys_pass_entry.pack(fill="x", pady=5)

        tk.Label(body, text="Company Fallback Email", bg="#f3f6f9").pack(anchor="w")
        self.sys_fall_entry = ttk.Entry(body, font=("Arial", 11)); self.sys_fall_entry.pack(fill="x", pady=5)
        self.sys_fall_entry.insert(0, "it-support@company.com")

        tk.Button(body, text="INITIALIZE SYSTEM", bg="#2c3e50", fg="white", 
                  font=("Arial", 10, "bold"), pady=15, command=self.create_account).pack(fill="x", pady=30)

    def create_account(self):
        user, pwd, conf = self.user_entry.get().strip(), self.pass_entry.get(), self.conf_entry.get()
        email = self.email_entry.get().strip()
        sys_email  = self.sys_email_entry.get().strip()
        sys_pass   = self.sys_pass_entry.get()
        sys_fall   = self.sys_fall_entry.get().strip()
        smtp_serv  = self.smtp_serv_entry.get().strip()
        smtp_port  = self.smtp_port_entry.get().strip()

        if not user or not pwd or not email or not sys_email or not sys_pass:
            messagebox.showwarning("Error", "All fields are required.")
            return
        if pwd != conf:
            messagebox.showerror("Error", "Passwords do not match.")
            return

        self.auth.update_system_settings(sys_email, sys_pass, sys_fall, smtp_serv, smtp_port)
        success, msg = self.auth.register_user(user, pwd, "System Administrator", email)
        if success:
            messagebox.showinfo("Success", "System initialized!")
            self.destroy()
            self.on_complete()
        else:
            messagebox.showerror("Error", msg)
