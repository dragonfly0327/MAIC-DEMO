import os
import json
import hashlib
import binascii
import secrets
import smtplib
import base64
import random
import configparser
import time
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# AUTHENTICATION & RBAC MANAGER
# ==========================================
class AuthManager:
    ROLES = ["System Administrator", "Top Management", "Engineering", "Sourcing", "Costing", "QAQC", "Pending"]
    # Permission Hierarchy: who can edit which roles
    # System Administrator > Top Management > all others
    ROLE_RANK = {
        "System Administrator": 100,
        "Top Management":       50,
        "Admin":               100,
        "Engineering":          10,
        "Sourcing":             10,
        "Costing":              10,
        "QAQC":                 10,
        "Pending":               0,
    }
    
    def __init__(self, server_path):
        self.server_path = server_path
        self.security_dir = os.path.join(self.server_path, "security")
        self.vault_path = os.path.join(self.security_dir, "users.json")
        self.settings_path = os.path.join(self.security_dir, "system_settings.json")
        self.active_codes = {} # Stores {key: (code, timestamp)}
        self.internal_key = "CONTXS_PROTECT_2026"
        self.CODE_EXPIRY = 120 # 2 minutes for all
        self.AUTH_EXPIRY = 120 # 2 minutes for all
        self.resend_log = {}   # {key: [timestamp, timestamp, ...]}
        
        try:
            os.makedirs(self.security_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create security directory on server: {e}")
            
        self.permissions_path = os.path.join(self.security_dir, "role_permissions.json")
        self.users = self._load_users()
        self.system_settings = self._load_settings()
        self.role_permissions = self._load_permissions()

    def _default_permissions(self):
        return {
            "System Administrator": ["BOM", "Sourcing", "Cycle Time", "Costing", "NPI", "WI", "Project Management"],
            "Top Management": ["BOM", "Sourcing", "Cycle Time", "Costing", "NPI", "WI", "Project Management"],
            "Engineering": ["BOM", "WI", "NPI"],
            "Sourcing": ["Sourcing", "Costing", "Cycle Time"],
            "Costing": ["Costing"],
            "QAQC": ["WI", "NPI"],
            "Pending": []
        }

    def _load_permissions(self):
        permissions = {}
        if os.path.exists(self.permissions_path):
            try:
                with open(self.permissions_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        permissions = data
            except Exception as e:
                print(f"[ERR_AUTH_006] Failed to load role permissions: {e}")
        
        if not permissions:
            permissions = self._default_permissions()
            try:
                with open(self.permissions_path, 'w', encoding='utf-8') as f:
                    json.dump(permissions, f, indent=4)
            except Exception:
                pass
        
        # Dynamically register any custom roles stored in permissions file
        for r_name in permissions.keys():
            if r_name not in self.ROLES:
                self.ROLES.append(r_name)
            if r_name not in self.ROLE_RANK:
                self.ROLE_RANK[r_name] = 10

        return permissions

    def _save_permissions(self):
        tmp_path = self.permissions_path + ".tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.role_permissions, f, indent=4)
            os.replace(tmp_path, self.permissions_path)
        except Exception as e:
            print(f"Failed to save role permissions: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _lock(self, lock_name, timeout=10):
        """Atomic directory-based locking for network shares with stale lock auto-recovery."""
        lock_path = os.path.join(self.security_dir, f"{lock_name}.lock")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                os.makedirs(lock_path)
                return True
            except FileExistsError:
                # Auto-heal stale lock folders left by crashed/terminated processes (>5 seconds old)
                try:
                    if os.path.exists(lock_path):
                        mtime = os.path.getmtime(lock_path)
                        if time.time() - mtime > 5:
                            print(f"[AuthManager] Auto-clearing stale lock folder: {lock_path}")
                            os.rmdir(lock_path)
                            continue
                except Exception as ex:
                    print(f"[AuthManager] Lock check warning: {ex}")
                time.sleep(0.2)
            except Exception as e:
                print(f"Lock error: {e}")
                return False
        return False

    def _unlock(self, lock_name):
        """Release the lock."""
        lock_path = os.path.join(self.security_dir, f"{lock_name}.lock")
        try:
            if os.path.exists(lock_path):
                os.rmdir(lock_path)
        except Exception:
            pass

    def _load_users(self):
        if os.path.exists(self.vault_path):
            try:
                with open(self.vault_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"[ERR_AUTH_002] Failed to load users: {e}")
                return {}
        return {}

    def _save_users(self):
        tmp_path = self.vault_path + ".tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=4)
            os.replace(tmp_path, self.vault_path)
        except Exception as e:
            err_msg = f"[ERR_AUTH_003] Failed to save users: {e}"
            print(err_msg)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERR_AUTH_005] Failed to load settings: {e}")
                return {}
        return {}

    def _save_settings(self):
        tmp_path = self.settings_path + ".tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.system_settings, f, indent=4)
            os.replace(tmp_path, self.settings_path)
        except Exception as e:
            print(f"Failed to save settings: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_role_permissions(self, role=None):
        self.role_permissions = self._load_permissions()
        if role:
            return self.role_permissions.get(role, self._default_permissions().get(role, []))
        return self.role_permissions

    def update_role_permissions(self, role, allowed_modules):
        if not self._lock("permissions"):
            return False, "Database busy [ERR_AUTH_007]. Please try again."
        try:
            self.role_permissions = self._load_permissions()
            self.role_permissions[role] = allowed_modules
            self._save_permissions()
            return True, f"Updated module permissions for role '{role}'."
        finally:
            self._unlock("permissions")

    def add_custom_role(self, role_name, initial_modules=None, rank=10):
        role_name = role_name.strip()
        if not role_name:
            return False, "Role name cannot be empty."
        
        if role_name in self.ROLES:
            return False, f"Role '{role_name}' already exists."

        if not self._lock("permissions"):
            return False, "Database busy [ERR_AUTH_008]. Please try again."

        try:
            if role_name not in self.ROLES:
                self.ROLES.append(role_name)
            self.ROLE_RANK[role_name] = rank

            self.role_permissions = self._load_permissions()
            self.role_permissions[role_name] = initial_modules if initial_modules is not None else []
            self._save_permissions()
            return True, f"Role '{role_name}' created successfully."
        finally:
            self._unlock("permissions")

    def _xor_crypt(self, data):
        """XOR-based obfuscation."""
        return "".join(chr(ord(c) ^ ord(self.internal_key[i % len(self.internal_key)])) 
                       for i, c in enumerate(data))

    def encrypt_secret(self, secret):
        if not secret: return ""
        return base64.b64encode(self._xor_crypt(secret).encode()).decode()

    def decrypt_secret(self, encrypted):
        if not encrypted: return ""
        try:
            return self._xor_crypt(base64.b64decode(encrypted).decode())
        except Exception:
            return ""

    def update_system_settings(self, email, app_pass, fallback, smtp_server="", smtp_port="465"):
        if not self._lock("settings"):
            return False, "Database busy [ERR_AUTH_004]. Please try again in a few seconds."
        
        try:
            self.system_settings = self._load_settings()
            self.system_settings.update({
                "email_user": email,
                "email_pass": self.encrypt_secret(app_pass) if app_pass else self.system_settings.get("email_pass", ""),
                "fallback_email": fallback,
                "smtp_server": smtp_server or "smtp.gmail.com",
                "smtp_port": int(smtp_port) if smtp_port else 465
            })
            self._save_settings()
            return True, "System settings updated successfully."
        finally:
            self._unlock("settings")

    def _get_smtp_connection(self, smtp_user, smtp_pass, smtp_server=None, smtp_port=None):
        """Returns an authenticated SMTP connection supporting SSL (465) and STARTTLS (587/others)."""
        if not smtp_user or not smtp_pass:
            raise ConnectionError("Error: Server disconnected. Configured SMTP credentials not found.")

        server_addr = smtp_server or self.system_settings.get("smtp_server")
        if not server_addr:
            raise ConnectionError("Error: Server disconnected. Configured SMTP server address not found.")

        port = int(smtp_port or self.system_settings.get("smtp_port", 465))

        try:
            if port == 465:
                server = smtplib.SMTP_SSL(server_addr, port, timeout=10)
            else:
                server = smtplib.SMTP(server_addr, port, timeout=10)
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(smtp_user, smtp_pass)
            return server
        except Exception as e:
            raise ConnectionError(f"Error: Server disconnected ({e})")

    def hash_password(self, password):
        """Hash a password for storing."""
        salt = hashlib.sha256(secrets.token_bytes(64)).hexdigest().encode('ascii')
        pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), 
                                    salt, 100000)
        pwdhash = binascii.hexlify(pwdhash)
        return (salt + pwdhash).decode('ascii')

    def verify_password(self, stored_password, provided_password):
        """Verify a stored password against one provided by user."""
        salt = stored_password[:64].encode('ascii')
        stored_hash = stored_password[64:].encode('ascii')
        pwdhash = hashlib.pbkdf2_hmac('sha512', 
                                    provided_password.encode('utf-8'), 
                                    salt, 100000)
        pwdhash = binascii.hexlify(pwdhash)
        return pwdhash == stored_hash

    def register_user(self, username, password, role, email=None):
        if not self._lock("users"):
            return False, "Database busy [ERR_AUTH_001]. Please try again."
            
        try:
            self.users = self._load_users()
            if username in self.users:
                return False, "User already exists"
            
            if role not in self.ROLES:
                return False, f"Invalid role. Choices: {', '.join(self.ROLES)}"

            hashed_pw = self.hash_password(password)
            self.users[username] = {
                "hash": hashed_pw,
                "role": role,
                "email": email
            }
            self._save_users()
            return True, "User registered successfully"
        finally:
            self._unlock("users")

    def verify_login(self, username, password):
        user_data = self.users.get(username)
        if not user_data:
            return None, "Invalid username or password"
        
        if self.verify_password(user_data["hash"], password):
            return {
                "username": username,
                "role": user_data["role"],
                "email": user_data.get("email", "")
            }, "Success"
        
        return None, "Invalid username or password"

    def has_users(self):
        return len(self.users) > 0

    def get_all_users(self):
        """Returns a list of all user data (excluding hashes for security)."""
        return [{"username": u, "role": d["role"]} for u, d in self.users.items()]

    def update_user_role(self, username, new_role):
        if not self._lock("users"): return False, "Database busy."
        try:
            self.users = self._load_users()
            if username in self.users and new_role in self.ROLES:
                self.users[username]["role"] = new_role
                self._save_users()
                return True, f"Role updated to {new_role}"
            return False, "User not found or invalid role"
        finally:
            self._unlock("users")

    def delete_user(self, username, requester_name, requester_password=None):
        if username == requester_name:
            return False, "You cannot delete your own account."
        
        if not self._lock("users"): return False, "Database busy."
        try:
            self.users = self._load_users()
            target_user = self.users.get(username)
            if not target_user:
                return False, f"User '{username}' not found."

            requester_user = self.users.get(requester_name)
            if not requester_user:
                return False, f"Requester admin account '{requester_name}' not found."

            # Verify admin password if provided
            if requester_password:
                if not self.verify_password(requester_user["hash"], requester_password):
                    return False, "Incorrect Admin Password."

            # Role Rank Check: Not allowed to delete user with the same or higher rank
            requester_role = requester_user.get("role", "")
            target_role = target_user.get("role", "")
            requester_rank = self.ROLE_RANK.get(requester_role, 0)
            target_rank = self.ROLE_RANK.get(target_role, 0)

            if requester_rank <= target_rank:
                return False, f"Permission Denied: User '{requester_name}' ({requester_role}) is not allowed to delete user '{username}' with equal or higher role rank ({target_role})."

            del self.users[username]
            self._save_users()
            return True, f"User '{username}' deleted successfully."
        finally:
            self._unlock("users")

    def notify_password_reset_acknowledgement(self, target_username, reset_by_user=None):
        """Sends an email notification acknowledging that target_username's password was reset and stating who reset it."""
        try:
            user_data = self.users.get(target_username, {})
            target_email = user_data.get("email")
            if not target_email or "@" not in target_email:
                target_email = self.system_settings.get("fallback_email")

            if not target_email or "@" not in target_email:
                return

            by_who = reset_by_user if reset_by_user else target_username
            reset_by_str = f"Administrator '{by_who}'" if by_who != target_username else "you (Self-Service Reset)"

            subject = "Security Notice: Password Reset Acknowledgement"
            body_text = (
                f"Hello {target_username},\n\n"
                f"This is an automated security notice to acknowledge that the password for your ContinuumX account ('{target_username}') was successfully reset by {reset_by_str}.\n\n"
                f"If you did NOT request or authorize this change, please contact your System Administrator immediately to secure your account."
            )

            import threading
            def _bg_send():
                try:
                    self._send_system_notification([target_email], subject, body_text)
                except Exception as ex:
                    print(f"Error sending password reset acknowledgement email: {ex}")

            threading.Thread(target=_bg_send, daemon=True).start()
        except Exception as e:
            print(f"Failed to trigger password reset notification: {e}")

    def register_self(self, username, password, email):
        if username in self.users:
            return False, "Username already taken."
        
        success, msg = self.register_user(username, password, "Pending", email)
        if success:
            # Notify Admin
            self.notify_admin_of_new_user(username, email)
            return True, "Registration successful! Please wait for an Admin to assign your role."
        return False, msg

    def notify_admin_of_new_user(self, username, user_email):
        # 1. Look for Top Management emails
        admin_emails = [u_data['email'] for u_data in self.users.values() 
                       if u_data['role'] == "Top Management" and u_data.get('email')]
        
        # 2. Fallback to system fallback email if no admin emails
        if not admin_emails:
            fallback = self.system_settings.get('fallback_email')
            if fallback: admin_emails.append(fallback)
        
        if not admin_emails: return # Nowhere to send

        self._send_system_notification(
            admin_emails, 
            "Action Required: New User Registration",
            f"A new user '{username}' ({user_email}) has registered and is waiting for role assignment."
        )

    def can_edit(self, editor_role, target_role):
        """Returns True if editor_role has permission to edit target_role."""
        editor_rank = self.ROLE_RANK.get(editor_role, 0)
        target_rank = self.ROLE_RANK.get(target_role, 0)
        # Editor must strictly outrank the target to edit them
        return editor_rank > target_rank

    def is_peer_top_management_edit(self, editor_role, target_role):
        """Returns True if a Top Management user is editing another Top Management."""
        return editor_role == "Top Management" and target_role == "Top Management"

    def send_target_verification(self, target_username):
        """Send a 2FA code to the TARGET user's email (for peer TM→TM edits)."""
        return self.send_verification_email(target_username)

    def update_user_full(self, target_username, admin_username, admin_password,
                         new_email=None, new_role=None, new_password=None,
                         target_2fa_code=None):
        if not self._lock("users"): return False, "Database busy [ERR_AUTH_001]."
        try:
            self.users = self._load_users()
            if not self.users and os.path.exists(self.vault_path):
                return False, "Vault inaccessible [ERR_AUTH_002]."
            # 1. Authenticate Admin
            admin_data = self.users.get(admin_username)
            if not admin_data or not self.verify_password(admin_data['hash'], admin_password):
                return False, "Administrative authentication failed."

            # 2. Permission Hierarchy Check
            admin_role  = admin_data.get('role', '')
            user_data   = self.users.get(target_username)
            if not user_data:
                return False, "Target user not found."
            
            target_role = user_data.get('role', '')

            if not self.can_edit(admin_role, target_role):
                return False, f"Permission denied: '{admin_role}' cannot modify a '{target_role}' account."

            # 3. Peer Top Management 2FA Check
            if self.is_peer_top_management_edit(admin_role, target_role):
                if not target_2fa_code:
                    return False, "2FA code from target user is required."
                if not self.validate_code(target_username, target_2fa_code):
                    return False, "Invalid or expired 2FA code from target user."

            # 4. Apply Updates
            if new_email is not None: user_data['email'] = new_email
            if new_role  is not None:
                # Prevent escalation beyond editor's own rank
                new_role_rank = self.ROLE_RANK.get(new_role, 0)
                admin_rank    = self.ROLE_RANK.get(admin_role, 0)
                if new_role_rank >= admin_rank:
                    return False, f"Cannot assign role '{new_role}': exceeds your permission level."
                user_data['role'] = new_role
            if new_password:
                user_data['hash'] = self.hash_password(new_password)
                self.notify_password_reset_acknowledgement(target_username, reset_by_user=admin_username)

            self._save_users()
            return True, f"Successfully updated user '{target_username}'."
        finally:
            self._unlock("users")

    # ==========================================
    # PASSWORD RESET & EMAIL LOGIC
    # ==========================================
    def _check_rate_limit(self, key):
        """Allow max 3 attempts within 5 minutes."""
        now = time.time()
        attempts = self.resend_log.get(key, [])
        # Keep only attempts from the last 5 minutes (300 seconds)
        attempts = [t for t in attempts if now - t < 300]
        self.resend_log[key] = attempts
        
        if len(attempts) >= 3:
            wait_time = int(300 - (now - attempts[0]))
            return False, f"Too many requests. Please wait {wait_time} seconds before resending."
        
        self.resend_log[key].append(now)
        return True, ""

    def send_verification_email(self, username):
        user_data = self.users.get(username)
        if not user_data:
            return False, "User not found"

        # Rate Limit Check
        allowed, rl_msg = self._check_rate_limit(username)
        if not allowed: return False, rl_msg

        # 1. Determine Target Email
        target_email = user_data.get('email')
        if not target_email or "@" not in target_email:
            target_email = self.system_settings.get('fallback_email')
        
        if not target_email:
            return False, "No email address configured for this user or company fallback."

        # 2. Get System Email Config from Server-Side settings
        smtp_user = self.system_settings.get('email_user')
        encrypted_pass = self.system_settings.get('email_pass')
        smtp_pass = self.decrypt_secret(encrypted_pass)

        if not smtp_user or not smtp_pass:
            return False, "System email not configured. Please contact an Administrator."

        # 3. Generate Code
        code = str(random.randint(100000, 999999))
        self.active_codes[username] = (code, time.time())

        # 4. Send Email
        try:
            msg = MIMEMultipart("alternative")
            msg['From']       = f"ContinuumX System <{smtp_user}>"
            msg['To']         = target_email
            msg['Subject']    = f"[ContinuumX] Password Reset Verification Code"
            msg['Reply-To']   = smtp_user
            msg['Message-ID'] = f"<{uuid.uuid4()}@continuum-system>"
            msg['X-Mailer']   = "ContinuumX Launcher v1.0"

            plain = f"""ContinuumX Security Alert

Hello {username},

A password reset has been requested for your ContinuumX account.

Your 6-digit verification code is: {code}

This code will expire in 2 minutes.

If you did NOT request this, please ignore this email. Your account remains secure.

---
This is an automated security message from ContinuumX Manufacturing Solutions.
Do not reply to this email.
"""
            html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:500px;margin:auto;color:#2c3e50;">
  <div style="background:#2c3e50;padding:20px;text-align:center;">
    <h2 style="color:#ecf0f1;margin:0;">ContinuumX</h2>
    <p style="color:#bdc3c7;margin:4px 0 0;">Secure Access Portal</p>
  </div>
  <div style="padding:30px;background:#f9f9f9;">
    <p>Hello <strong>{username}</strong>,</p>
    <p>A password reset was requested for your account. Use the code below to proceed:</p>
    <div style="text-align:center;margin:25px 0;">
      <span style="font-size:32px;font-weight:bold;letter-spacing:10px;color:#2c3e50;background:#ecf0f1;padding:15px 25px;border-radius:8px;display:inline-block;">{code}</span>
    </div>
    <p style="color:#e74c3c;"><strong>⏱ This code expires in 2 minutes.</strong></p>
    <p style="color:#7f8c8d;font-size:13px;">If you did not request this, you can safely ignore this email. Your account has not been changed.</p>
  </div>
  <div style="padding:15px;text-align:center;background:#ecf0f1;color:#95a5a6;font-size:11px;">
    © 2026 Continuum Xolutions PLT · This is an automated message, do not reply.
  </div>
</body></html>"""

            msg.attach(MIMEText(plain, 'plain', 'utf-8'))
            msg.attach(MIMEText(html,  'html',  'utf-8'))

            server = self._get_smtp_connection(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            
            return True, f"Verification code sent to {target_email[:3]}***{target_email[target_email.index('@'):]}"
        except Exception as e:
            return False, f"Failed to send email: {str(e)}"

    def validate_code(self, username, entered_code):
        if username in self.active_codes:
            stored_code, timestamp = self.active_codes[username]
            if time.time() - timestamp > self.CODE_EXPIRY:
                del self.active_codes[username]
                return False
            return stored_code == entered_code
        return False

    def reset_password(self, username, new_password, code):
        """Standard User Reset with 2FA."""
        if not self.validate_code(username, code):
            return False, "Invalid or expired verification code"
        
        if not self._lock("users"): return False, "Database busy."
        try:
            self.users = self._load_users()
            user_data = self.users.get(username)
            if user_data:
                user_data["hash"] = self.hash_password(new_password)
                del self.active_codes[username]
                self._save_users()
                self.notify_password_reset_acknowledgement(username, reset_by_user=username)
                return True, "Password changed successfully"
            return False, "User not found"
        finally:
            self._unlock("users")

    def admin_reset_password(self, username, new_password, reset_by_user="Admin"):
        """Admin override without 2FA."""
        if not self._lock("users"): return False, "Database busy."
        try:
            self.users = self._load_users()
            user_data = self.users.get(username)
            if user_data:
                user_data["hash"] = self.hash_password(new_password)
                self._save_users()
                self.notify_password_reset_acknowledgement(username, reset_by_user=reset_by_user)
                return True, f"Password for {username} reset successfully."
            return False, "User not found"
        finally:
            self._unlock("users")

    # ==========================================
    # SYSTEM SETTINGS VERIFICATION
    # ==========================================
    def send_system_auth_email(self):
        """Sends a code to the CURRENT system email to authorize changes."""
        smtp_user = self.system_settings.get('email_user')
        if not smtp_user:
            return False, "No system email configured yet."
            
        return self._send_code_to_email(smtp_user, "Authorize System Changes", "_system_auth_")

    def send_new_system_verify_email(self, email, app_pass, fallback, smtp_server="", smtp_port="465"):
        """Sends a code to the NEW system email to verify it works."""
        return self._send_code_to_email(
            email, "Verify New System Email", "_system_new_verify_",
            custom_creds=(email, app_pass, smtp_server or "smtp.gmail.com", int(smtp_port or 465))
        )

    def _send_code_to_email(self, target_email, subject_prefix, code_key_prefix, custom_creds=None):
        # Rate Limit Check
        rl_key = code_key_prefix + target_email
        allowed, rl_msg = self._check_rate_limit(rl_key)
        if not allowed: return False, rl_msg

        # 1. Get Credentials
        if custom_creds:
            smtp_user = custom_creds[0]
            smtp_pass = custom_creds[1]
            smtp_server = custom_creds[2] if len(custom_creds) > 2 else self.system_settings.get("smtp_server", "smtp.gmail.com")
            smtp_port   = custom_creds[3] if len(custom_creds) > 3 else self.system_settings.get("smtp_port", 465)
        else:
            smtp_user = self.system_settings.get('email_user')
            encrypted_pass = self.system_settings.get('email_pass')
            smtp_pass = self.decrypt_secret(encrypted_pass)
            smtp_server = self.system_settings.get("smtp_server", "smtp.gmail.com")
            smtp_port   = self.system_settings.get("smtp_port", 465)

        if not smtp_user or not smtp_pass:
            return False, "Email credentials missing."

        # 2. Generate Code
        code = str(random.randint(100000, 999999))
        self.active_codes[code_key_prefix + target_email] = (code, time.time())

        # 3. Send Email
        try:
            msg = MIMEMultipart("alternative")
            msg['From']       = f"ContinuumX System <{smtp_user}>"
            msg['To']         = target_email
            msg['Subject']    = f"[ContinuumX] {subject_prefix} - Verification Code"
            msg['Reply-To']   = smtp_user
            msg['Message-ID'] = f"<{uuid.uuid4()}@continuum-system>"
            msg['X-Mailer']   = "ContinuumX Launcher v2.0"

            plain = f"""ContinuumX Security Code

Your 6-digit verification code is: {code}

Purpose: {subject_prefix}
This code will expire in 2 minutes.

If you did not request this code, please contact your system administrator immediately.

---
This is an automated security message from ContinuumX Manufacturing Solutions.
Do not reply to this email.
"""
            html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:500px;margin:auto;color:#2c3e50;">
  <div style="background:#2c3e50;padding:20px;text-align:center;">
    <h2 style="color:#ecf0f1;margin:0;">ContinuumX</h2>
    <p style="color:#bdc3c7;margin:4px 0 0;">Secure Access Portal</p>
  </div>
  <div style="padding:30px;background:#f9f9f9;">
    <p>A verification code has been requested for: <strong>{subject_prefix}</strong></p>
    <div style="text-align:center;margin:25px 0;">
      <span style="font-size:32px;font-weight:bold;letter-spacing:10px;color:#2c3e50;background:#ecf0f1;padding:15px 25px;border-radius:8px;display:inline-block;">{code}</span>
    </div>
    <p style="color:#e74c3c;"><strong>⏱ This code expires in 2 minutes.</strong></p>
    <p style="color:#7f8c8d;font-size:13px;">If you did not request this, contact your system administrator immediately.</p>
  </div>
  <div style="padding:15px;text-align:center;background:#ecf0f1;color:#95a5a6;font-size:11px;">
    © 2026 Continuum Xolutions PLT · This is an automated message, do not reply.
  </div>
</body></html>"""

            msg.attach(MIMEText(plain, 'plain', 'utf-8'))
            msg.attach(MIMEText(html,  'html',  'utf-8'))

            server = self._get_smtp_connection(smtp_user, smtp_pass, smtp_server, smtp_port)
            server.send_message(msg)
            server.quit()
            
            return True, f"Code sent to {target_email}"
        except Exception as e:
            return False, f"Email failed: {str(e)}"

    def validate_system_code(self, target_email, code, code_key_prefix):
        key = code_key_prefix + target_email
        if key in self.active_codes:
            stored_code, timestamp = self.active_codes[key]
            # Enforce AUTH_EXPIRY for system authorization
            if time.time() - timestamp > self.AUTH_EXPIRY:
                del self.active_codes[key]
                return False
            
            if stored_code == code:
                del self.active_codes[key]
                return True
        return False

    def _send_system_notification(self, recipients, subject, body_text):
        smtp_user   = self.system_settings.get('email_user')
        encrypted_pass = self.system_settings.get('email_pass')
        smtp_pass   = self.decrypt_secret(encrypted_pass)
        smtp_server = self.system_settings.get("smtp_server", "smtp.gmail.com")
        smtp_port   = self.system_settings.get("smtp_port", 465)

        if not smtp_user or not smtp_pass: return

        try:
            msg = MIMEMultipart("alternative")
            msg['From']       = f"ContinuumX System <{smtp_user}>"
            msg['To']         = ", ".join(recipients)
            msg['Subject']    = f"[ContinuumX] {subject}"
            msg['Reply-To']   = smtp_user
            msg['Message-ID'] = f"<{uuid.uuid4()}@continuum-system>"
            msg['X-Mailer']   = "ContinuumX Launcher v2.0"

            html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:500px;margin:auto;color:#2c3e50;">
  <div style="background:#2c3e50;padding:20px;text-align:center;">
    <h2 style="color:#ecf0f1;margin:0;">ContinuumX Admin Alert</h2>
  </div>
  <div style="padding:30px;background:#f9f9f9;">
    <p>{body_text}</p>
  </div>
  <div style="padding:15px;text-align:center;background:#ecf0f1;color:#95a5a6;font-size:11px;">
    © 2026 Continuum Xolutions PLT · Automated notification, do not reply.
  </div>
</body></html>"""

            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            msg.attach(MIMEText(html,      'html',  'utf-8'))

            server = self._get_smtp_connection(smtp_user, smtp_pass, smtp_server, smtp_port)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Failed to send admin notification: {e}")
