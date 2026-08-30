import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
if _curr_dir not in sys.path:
    sys.path.insert(0, _curr_dir)

from system_login import SystemLoginDialog, get_launcher_user_session, verify_launcher_authorization
verify_launcher_authorization("BOM")

import tkinter as tk
from tkinter import ttk
from tkinter.ttk import Notebook, Frame, Button, Label
from utils import SemanticMessageBox as messagebox

# ==============================================================================
# --- UI AUTOFIT / DEPLOYMENT CONFIGURATION ---
# Set AUTOFIT_TO_SCREEN to True when deploying to users' laptops so main windows
# automatically maximize to fit their screens. Set to False for fixed developer mode.
# ==============================================================================
AUTOFIT_TO_SCREEN = True

# --- Global Auto-Centering & Premium Styling Monkeypatch ---
_orig_toplevel_init = tk.Toplevel.__init__
_orig_tk_init = tk.Tk.__init__

_orig_button_init = tk.Button.__init__
_orig_frame_init = tk.Frame.__init__
_orig_labelframe_init = tk.LabelFrame.__init__
_orig_label_init = tk.Label.__init__

def patched_button_init(self, master=None, cnf={}, **kw):
    _orig_button_init(self, master, cnf, **kw)
    try:
        toplevel = self.winfo_toplevel()
        is_main = isinstance(toplevel, tk.Tk)
        text = str(self.cget("text")).lower().strip()
        current_bg = str(self.cget("bg")).lower()
        is_destructive = any(x in text for x in ("delete", "remove", "overwrite", "warning")) or current_bg in ("#dc3545", "#c82333")
        is_small = (any(x == text for x in ("add new", "+ add new", "➕ add new", "prev", "next")) or 
                    any(x in text for x in ("manage master list", "◀", "▶")) or
                    text in ("<", ">", "|<", ">|"))
        
        if not is_main:
            # Subpages: all buttons are dark blue except red ones
            if is_destructive:
                bg_color = "#dc3545"
                fg_color = "white"
                hover_color = "#c82333"
            else:
                bg_color = "#1A365D"
                fg_color = "white"
                hover_color = "#0077B6"
                
            if is_small:
                self.configure(
                    bg=bg_color,
                    fg=fg_color,
                    activebackground=hover_color,
                    activeforeground=fg_color,
                    font=("Segoe UI", 9, "bold"),
                    bd=0,
                    relief="flat",
                    cursor="hand2",
                    height=1,
                    pady=2
                )
            else:
                self.configure(
                    bg=bg_color,
                    fg=fg_color,
                    activebackground=hover_color,
                    activeforeground=fg_color,
                    font=("Segoe UI", 10, "bold"),
                    bd=0,
                    relief="flat",
                    cursor="hand2",
                    height=1,
                    pady=6
                )
        else:
            # Main page: original styling layout
            is_cancel = any(x in text for x in ("cancel", "close", "revert", "no", "logout", "skip", "exit"))
            if is_cancel:
                bg_color = "#E2E8F0"
                fg_color = "#2D3748"
                hover_color = "#CBD5E0"
            elif is_destructive:
                bg_color = "#dc3545" if current_bg in ("#dc3545", "#c82333") else "#2ead4e"
                fg_color = "white"
                hover_color = "#c82333" if current_bg in ("#dc3545", "#c82333") else "#248a3e"
            else:
                bg_color = "#1A365D"
                fg_color = "white"
                hover_color = "#0077B6"
                
            self.configure(
                bg=bg_color,
                fg=fg_color,
                activebackground=hover_color,
                activeforeground=fg_color,
                font=("Segoe UI", 10, "bold"),
                bd=0,
                relief="flat",
                cursor="hand2",
                height=1
            )
            
        def on_enter(e):
            if str(self.cget("state")) != "disabled":
                self.configure(bg=hover_color)
        def on_leave(e):
            if str(self.cget("state")) != "disabled":
                self.configure(bg=bg_color)
        self.bind("<Enter>", on_enter, add="+")
        self.bind("<Leave>", on_leave, add="+")
    except:
        pass

def patched_frame_init(self, master=None, cnf={}, **kw):
    if "bg" not in kw and "background" not in kw:
        kw["bg"] = "#EBF8FF"
    _orig_frame_init(self, master, cnf, **kw)

def patched_labelframe_init(self, master=None, cnf={}, **kw):
    if "bg" not in kw and "background" not in kw:
        kw["bg"] = "#EBF8FF"
    if "fg" not in kw and "foreground" not in kw:
        kw["fg"] = "#1A365D"
    if "font" not in kw:
        kw["font"] = ("Segoe UI", 10, "bold")
    _orig_labelframe_init(self, master, cnf, **kw)

def patched_label_init(self, master=None, cnf={}, **kw):
    if "bg" not in kw and "background" not in kw:
        kw["bg"] = "#EBF8FF"
    if "fg" not in kw and "foreground" not in kw:
        kw["fg"] = "#1A365D"
    if "font" not in kw:
        kw["font"] = ("Segoe UI", 10)
    _orig_label_init(self, master, cnf, **kw)

tk.Button.__init__ = patched_button_init
tk.Frame.__init__ = patched_frame_init
tk.LabelFrame.__init__ = patched_labelframe_init
tk.Label.__init__ = patched_label_init

class PatchedTTKButton(tk.Button):
    def __init__(self, master=None, **kw):
        kw.pop("style", None)
        kw.pop("padding", None)
        kw.setdefault("relief", "flat")
        kw.setdefault("bd", 0)
        kw.setdefault("padx", 15)
        kw.setdefault("pady", 6)
        kw.setdefault("cursor", "hand2")
        super().__init__(master, **kw)

tk.ttk.Button = PatchedTTKButton

# --- Global Treeview Left-Alignment Monkeypatch ---
_orig_treeview_heading = ttk.Treeview.heading
def _patched_treeview_heading(self, column, option=None, **kw):
    if option is None and not kw:
        return _orig_treeview_heading(self, column)
    if isinstance(option, str) and not kw:
        return _orig_treeview_heading(self, column, option)
    if isinstance(option, dict):
        kw.update(option)
        option = None
    kw["anchor"] = "w"
    if option is not None:
        return _orig_treeview_heading(self, column, option, **kw)
    return _orig_treeview_heading(self, column, **kw)

ttk.Treeview.heading = _patched_treeview_heading

_orig_treeview_column = ttk.Treeview.column
def _patched_treeview_column(self, column, option=None, **kw):
    if option is None and not kw:
        return _orig_treeview_column(self, column)
    if isinstance(option, str) and not kw:
        return _orig_treeview_column(self, column, option)
    if isinstance(option, dict):
        kw.update(option)
        option = None
    kw["anchor"] = "w"
    if option is not None:
        return _orig_treeview_column(self, column, option, **kw)
    return _orig_treeview_column(self, column, **kw)

ttk.Treeview.column = _patched_treeview_column

def _apply_premium_global_styling(window):
    try:
        window.configure(bg="#EBF8FF")
    except:
        pass
        
    def _style_widget(widget):
        try:
            class_name = widget.__class__.__name__
            if class_name in ("Button", "PatchedTTKButton") or isinstance(widget, tk.Button):
                text = str(widget.cget("text")).lower().strip()
                current_bg = str(widget.cget("bg")).lower()
                
                # Check for Destructive/Red buttons
                is_destructive = any(x in text for x in ("delete", "remove", "overwrite", "warning")) or current_bg in ("#dc3545", "#c82333")
                
                is_main_page = isinstance(window, tk.Tk)
                
                if not is_main_page:
                    # Secondary dialog/wizard pages: all buttons are dark blue except red/destructive ones
                    if is_destructive:
                        bg_color = "#dc3545"
                        fg_color = "white"
                        hover_color = "#c82333"
                    else:
                        bg_color = "#1A365D"
                        fg_color = "white"
                        hover_color = "#0077B6"
                        
                    widget.configure(
                        bg=bg_color,
                        fg=fg_color,
                        activebackground=hover_color,
                        activeforeground=fg_color,
                        font=("Segoe UI", 10, "bold"),
                        bd=0,
                        relief="flat",
                        cursor="hand2",
                        pady=6
                    )
                else:
                    # Main page: original styling layout (including Cancel and Green buttons)
                    is_cancel = any(x in text for x in ("cancel", "close", "revert", "no", "logout", "skip", "exit"))
                    if is_cancel:
                        bg_color = "#E2E8F0"
                        fg_color = "#2D3748"
                        hover_color = "#CBD5E0"
                    elif is_destructive:
                        bg_color = "#dc3545" if current_bg in ("#dc3545", "#c82333") else "#2ead4e"
                        fg_color = "white"
                        hover_color = "#c82333" if current_bg in ("#dc3545", "#c82333") else "#248a3e"
                    else: # Primary
                        bg_color = "#1A365D"
                        fg_color = "white"
                        hover_color = "#0077B6"
                        
                    widget.configure(
                        bg=bg_color,
                        fg=fg_color,
                        activebackground=hover_color,
                        activeforeground=fg_color,
                        font=("Segoe UI", 10, "bold"),
                        bd=0,
                        relief="flat",
                        cursor="hand2"
                    )
                
                # Force button width to auto-size only if it was not explicitly configured
                try:
                    if int(widget.cget("width")) == 0:
                        widget.configure(width=0)
                except:
                    pass
                
                # Apply hover effects
                def on_enter(e, btn=widget, bg=bg_color, hbg=hover_color):
                    try:
                        if str(btn.cget("state")) != "disabled":
                            btn.configure(bg=hbg)
                    except: pass
                def on_leave(e, btn=widget, bg=bg_color):
                    try:
                        if str(btn.cget("state")) != "disabled":
                            btn.configure(bg=bg)
                    except: pass
                    
                widget.bind("<Enter>", on_enter, add="+")
                widget.bind("<Leave>", on_leave, add="+")
                
                try:
                    widget.configure(padx=15, pady=5)
                except:
                    pass
                    
            elif class_name in ("Frame", "LabelFrame") or isinstance(widget, (tk.Frame, tk.LabelFrame)):
                try:
                    current_bg = str(widget.cget("bg")).lower()
                    if any(x in current_bg for x in ["#f2f2f2", "#f0f0f0", "#ebebeb", "#f8f9fa", "systembuttonface"]):
                        parent_bg = str(widget.master.cget("bg")).lower()
                        if parent_bg and parent_bg != "systembuttonface" and not any(x in parent_bg for x in ["#f2f2f2", "#f0f0f0", "#ebebeb", "#f8f9fa"]):
                            widget.configure(bg=parent_bg)
                        else:
                            widget.configure(bg="#EBF8FF")
                except:
                    pass
            elif class_name == "Label" or isinstance(widget, tk.Label):
                try:
                    parent_bg = widget.master.cget("bg")
                    if parent_bg and parent_bg != "systembuttonface":
                        widget.configure(bg=parent_bg)
                except:
                    pass
        except:
            pass

        try:
            for child in widget.winfo_children():
                _style_widget(child)
        except:
            pass

    _style_widget(window)
def is_main_workspace(window):
    try:
        cls_name = window.__class__.__name__
        if "Dialog" in cls_name or "Popup" in cls_name or cls_name in ("SystemLoginDialog", "ConfirmCloseDialog", "ConfirmationDialog", "AlertDialog", "PromptMissingUOMDialog", "SourcingCancelWarningDialog", "CategoryInputDialog", "SortRecordsDialog"):
            return False

        try:
            if window.transient():
                return False
        except:
            pass

        title = str(window.title()).lower()
        if any(x in title for x in ("login", "confirm", "warning", "prompt", "alert", "error", "message", "checklist", "change log", "sort", "filter")):
            return False

        main_keywords = [
            "start sourcing from verified boms", "dispatch sourcing results to costing",
            "dispatch cycle time results to costing", "sourcing master workflow",
            "dispatch sourcing workflow", "radysis sourcing operations", "radysis bom management",
            "radysis cycle time management", "radysis costing management", "sourcing data maintenance",
            "unit of measurement", "uom conversion", "customer alternative", "assign moq", "target price"
        ]
        for kw in main_keywords:
            if kw in title:
                return True

        if cls_name in ("SourcingApp", "CycleTimeApp", "BOMApp", "CostingApp", "SourcingMasterWindow", "MainApp"):
            return True
    except:
        pass
    return False

def is_mdm_window(window):
    """Returns True if the window is an MDM maintenance dialog (except Sourcing Data Maintenance)."""
    try:
        title = str(window.title()).lower()
        if "sourcing data" in title or "sourcing app" in title:
            return False  # Sourcing Data Maintenance is allowed to be zoomed by default!
        if any(x in title for x in ("alternative", "uom", "conversion", "maintenance", "master data")):
            return True
        cls_name = window.__class__.__name__
        if cls_name in ("CustomerAlternativeMPNMaintenanceDialog", "UOMConversionMaintenanceDialog"):
            return True
    except:
        pass
    return False

def _center_window_on_master_or_screen(window):
    if getattr(window, '_is_autocomplete_popup', False):
        return

    cls_name = window.__class__.__name__
    title_str = ""
    try: title_str = str(window.title()).lower()
    except: pass

    is_prompt_or_dialog = (
        not is_main_workspace(window)
        or cls_name in ("SystemLoginDialog", "ConfirmCloseDialog", "ConfirmationDialog", "AlertDialog", "PromptMissingUOMDialog", "SourcingCancelWarningDialog", "CategoryInputDialog")
        or any(x in title_str for x in ("login", "confirm", "warning", "prompt", "alert", "error", "message", "checklist"))
    )

    if is_prompt_or_dialog:
        try:
            window.update_idletasks()
            sw = window.winfo_screenwidth()
            sh = window.winfo_screenheight()
            w = window.winfo_width()
            h = window.winfo_height()
            if w <= 1 or h <= 1:
                try:
                    geom = window.geometry()
                    size_part = geom.split("+")[0]
                    w, h = map(int, size_part.split("x"))
                except:
                    w, h = window.winfo_reqwidth(), window.winfo_reqheight()
            if w <= 1 or h <= 1:
                w, h = 550, 300
            
            master = getattr(window, 'master', None)
            if master and hasattr(master, 'winfo_ismapped') and master.winfo_ismapped():
                mw = master.winfo_width()
                mh = master.winfo_height()
                mx = master.winfo_rootx()
                my = master.winfo_rooty()
                x = max(0, mx + (mw - w) // 2)
                y = max(0, my + (mh - h) // 2)
            else:
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
            window.geometry(f"{w}x{h}+{x}+{y}")
        except:
            pass
        return

    try:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        w, h = 1200, 700
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")
        window.update_idletasks()
    except:
        pass

    if AUTOFIT_TO_SCREEN and not getattr(window, '_skip_autofit', False):
        try:
            window.state('zoomed')
            return
        except:
            pass
        
    try:
        window.update_idletasks()
    except:
        pass
        
    master = None
    try:
        master = window.master
    except:
        pass
        
    window_width = window.winfo_width()
    window_height = window.winfo_height()
    
    if window_width <= 1 or window_height <= 1:
        try:
            geom = window.geometry()
            size_part = geom.split("+")[0]
            w, h = map(int, size_part.split("x"))
            window_width = w
            window_height = h
        except:
            window_width = 400
            window_height = 300

    skip_fit = getattr(window, '_skip_autofit', False)

    is_display_changes = "display changes" in title_str or "history" in title_str or "change log" in title_str

    if is_display_changes:
        window_width = 1150
        window_height = 600
    elif not skip_fit and ((window_width >= 900 and window_height >= 550) or is_main_workspace(window)):
        window_width = 1200
        window_height = 700

    try:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max(0, (screen_width // 2) - (window_width // 2))
        y = max(0, (screen_height // 2) - (window_height // 2))
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        if AUTOFIT_TO_SCREEN and not skip_fit and not is_mdm_window(window) and (window_width >= 1000 or is_main_workspace(window)):
            try:
                window.state('zoomed')
            except:
                pass
        return
    except:
        pass

def patched_toplevel_init(self, master=None, cnf={}, **kw):
    _orig_toplevel_init(self, master, cnf, **kw)
    self._explicitly_withdrawn = True
    
    _orig_withdraw = self.withdraw
    def custom_withdraw():
        self._explicitly_withdrawn = True
        _orig_withdraw()
    self.withdraw = custom_withdraw
    
    _orig_deiconify = self.deiconify
    def custom_deiconify():
        self._explicitly_withdrawn = False
        _orig_deiconify()
    self.deiconify = custom_deiconify

    try:
        _orig_withdraw(self)
    except:
        pass

    def _do_center_and_style():
        is_dialog = False
        try:
            class_name = self.__class__.__name__
            if class_name in ("Dialog", "SimpleDialog", "_QueryDialog", "_QueryString", "_QueryInteger", "_QueryDouble", "CategoryInputDialog", "BaseDialog"):
                is_dialog = True
            title = self.title()
            if any(x in title for x in ("Warning", "Error", "Info", "Question", "Message", "Confirm", "Set MOQs", "Categories")):
                is_dialog = True
        except:
            pass

        try:
            _center_window_on_master_or_screen(self)
        except:
            pass

        if not is_dialog:
            try:
                _apply_premium_global_styling(self)
            except:
                pass
        try:
            if not self._explicitly_withdrawn:
                _orig_deiconify(self)
        except:
            pass
    self.after(65, _do_center_and_style)

def patched_tk_init(self, screenName=None, baseName=None, className='Tk', useTk=True, sync=False, use=None):
    _orig_tk_init(self, screenName, baseName, className, useTk, sync, use)
    def _do_center_and_style():
        try: _center_window_on_master_or_screen(self)
        except: pass
        try: _apply_premium_global_styling(self)
        except: pass
    self.after(65, _do_center_and_style)

tk.Toplevel.__init__ = patched_toplevel_init
tk.Tk.__init__ = patched_tk_init

_orig_geometry = tk.Toplevel.geometry

def patched_geometry(self, new_geometry=None):
    if new_geometry is None:
        return _orig_geometry(self)
        
    try:
        is_dialog = False
        try:
            class_name = self.__class__.__name__
            if class_name in ("Dialog", "SimpleDialog", "_QueryDialog", "_QueryString", "_QueryInteger", "_QueryDouble", "CategoryInputDialog", "BaseDialog"):
                is_dialog = True
            title = self.title()
            if any(x in title for x in ("Warning", "Error", "Info", "Question", "Message", "Confirm", "Set MOQs", "Categories")):
                is_dialog = True
        except:
            pass

        if is_dialog:
            return _orig_geometry(self, new_geometry)

        if "+" not in new_geometry and "-" not in new_geometry:
            w, h = map(int, new_geometry.split("x"))
            
            skip_fit = getattr(self, "_skip_autofit", False)
            
            # --- OVERRIDE LARGE DATABASE WINDOWS TO FIXED 1200x700 AND CENTER ON SCREEN ---
            if (w >= 900 and h >= 550) or is_main_workspace(self):
                w, h = 1200, 700
                
            try:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                x = max(0, (screen_width // 2) - (w // 2))
                y = max(0, (screen_height // 2) - (h // 2))
            except:
                x, y = 50, 50
                    
            _orig_geometry(self, f"{w}x{h}+{x}+{y}")

            # --- Window State Transition Auto-Recentering Listener ---
            if not getattr(self, '_has_unmaximize_listener', False):
                self._has_unmaximize_listener = True
                self._prev_wm_state = getattr(self, '_prev_wm_state', 'zoomed')
                def _on_window_unmaximize(event, win=self, target_w=w, target_h=h):
                    if event.widget == win:
                        try:
                            curr_st = win.wm_state()
                            prev_st = getattr(win, '_prev_wm_state', 'zoomed')
                            if curr_st == 'normal' and prev_st == 'zoomed':
                                _sw = win.winfo_screenwidth()
                                _sh = win.winfo_screenheight()
                                _cx = max(0, (_sw - target_w) // 2)
                                _cy = max(0, (_sh - target_h) // 2)
                                _orig_geometry(win, f"{target_w}x{target_h}+{_cx}+{_cy}")
                            if curr_st != prev_st:
                                win._prev_wm_state = curr_st
                        except Exception:
                            pass
                try:
                    self.bind("<Configure>", _on_window_unmaximize, add="+")
                except Exception:
                    pass
            
            if AUTOFIT_TO_SCREEN and not skip_fit and not is_mdm_window(self) and (w >= 1000 or is_main_workspace(self)):
                try:
                    self.state('zoomed')
                except:
                    pass
            return
    except:
        pass
        
    return _orig_geometry(self, new_geometry)

tk.Toplevel.geometry = patched_geometry

_orig_toplevel_deiconify = tk.Toplevel.deiconify
_orig_tk_deiconify = tk.Tk.deiconify

def patched_toplevel_deiconify(self):
    _orig_toplevel_deiconify(self)
    try:
        if AUTOFIT_TO_SCREEN and is_main_workspace(self):
            self.state('zoomed')
    except:
        pass

def patched_tk_deiconify(self):
    _orig_tk_deiconify(self)
    try:
        if AUTOFIT_TO_SCREEN and is_main_workspace(self):
            self.state('zoomed')
    except:
        pass

tk.Toplevel.deiconify = patched_toplevel_deiconify
tk.Tk.deiconify = patched_tk_deiconify

_orig_grab_set = tk.Toplevel.grab_set
_orig_grab_release = tk.Toplevel.grab_release

def patched_grab_set(self):
    self._has_grab = True
    try:
        _orig_grab_set(self)
    except:
        pass
    if not hasattr(self, '_destroy_binding_applied_grab'):
        self._destroy_binding_applied_grab = True
        def on_destroy(event):
            if event.widget == self:
                self._has_grab = False
        try:
            self.bind("<Destroy>", on_destroy, add="+")
        except:
            pass

def patched_grab_release(self):
    self._has_grab = False
    try:
        _orig_grab_release(self)
    except:
        pass

tk.Toplevel.grab_set = patched_grab_set
tk.Toplevel.grab_release = patched_grab_release

# --- Custom Imports ---
from utils import DATA_PATH
from bomformatter import verify_bom_workflow, assign_moq_workflow, input_target_price_workflow, dispatch_rfq_workflow
# -----------------------------------------------------------------

# --- ROLE DEFINITIONS (Centralized Access Control Data) ---
ROLE_RESTRICTIONS = {
    'Sourcing': [],
    'Engineering': [],
    'Viewer': [],
    'Admin': [], 
}
ALL_TABS = ['BOM'] 
# ----------------------------------------------------------

class MainApp:
    def __init__(self, master, user_name, user_role, logout_callback):
        self.master = master # The Tk root
        self.user_role = user_role
        self.user_name = user_name
        self.logout_callback = logout_callback # Function to return to login/exit
        
        # Configure global ttk style configurations for consistency and immediate loading
        try:
            import tkinter.ttk as ttk
            style = ttk.Style(self.master)
            style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
            style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        except:
            pass
        
        # Create the Main Application Window as a Toplevel
        self.window = tk.Toplevel(master)
        self.window.withdraw() # Hide it immediately so it doesn't show as a big empty window during login
        self.window.user_name = user_name
        self.window.user_role = user_role
        self.window.title("Radysis BOM Management - " + user_name + " (" + user_role + ")")
        self.window.geometry("1200x700")
        self.window.protocol("WM_DELETE_WINDOW", self.logout_callback)

        session = None
        try:
            from system_login import get_launcher_user_session
            session = get_launcher_user_session()
        except Exception:
            pass
            
        logged_user = session.get("username") if session else user_name
        self.user_name = logged_user
        self.window.user_name = logged_user
        self.window.title("Radysis BOM Management - " + logged_user + " (" + user_role + ")")
        self.window.deiconify() # Show the main window

        # --- Add Status Bar ---
        self.window.status_bar = tk.Label(self.window, text="BOM Microservice Active", bd=1, relief=tk.SUNKEN, anchor=tk.CENTER, font=("Arial", 9, "bold"))
        self.window.status_bar.pack(side='bottom', fill='x')

        # --- Exit / Close & Switch PIC buttons ---
        self.logout_btn = self._create_premium_button(
            self.window, 
            text="🚪 Exit / Return to Launcher", 
            command=self.logout_callback,
            bg_color="#1A365D",
            hover_bg="#0077B6"
        )
        self.logout_btn.pack(side='bottom', fill='x', padx=10, pady=(2, 5))

        self.login_btn = self._create_premium_button(
            self.window, 
            text=f"🔑 Switch User Login (Active User: {self.user_name})", 
            command=self._switch_login,
            bg_color="#2B6CB0",
            hover_bg="#3182CE"
        )
        self.login_btn.pack(side='bottom', fill='x', padx=10, pady=(5, 2))
        
        self.notebook = Notebook(self.window) 
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self._previous_tab = None
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._initialize_tab_frames()
        self._create_all_ui()
        self._apply_role_restrictions()

    def check_active_subwindow(self):
        root = getattr(self.window, 'master', self.window)
        for child_name, child_widget in list(root.children.items()):
            if isinstance(child_widget, tk.Toplevel) and child_widget != self.window:
                try:
                    if getattr(child_widget, '_is_autocomplete_popup', False):
                        continue
                    if child_widget.winfo_exists() and getattr(child_widget, '_has_grab', False):
                        if child_widget.state() != 'withdrawn' and child_widget.winfo_viewable():
                            return child_widget
                except:
                    pass
        return None

    def _warn_and_restore_active_window(self, active_win):
        messagebox.showwarning("Active Workflow Detected", "An active task window is already open. Please complete or close the current window before accessing other functions.")
        try:
            active_win.deiconify()
            active_win.lift()
            active_win.focus_force()
        except:
            pass

    def _on_tab_changed(self, event):
        active_win = self.check_active_subwindow()
        if active_win:
            self._warn_and_restore_active_window(active_win)
            if self._previous_tab is not None:
                try:
                    self.notebook.select(self._previous_tab)
                except:
                    pass
            return
        
        try:
            self._previous_tab = self.notebook.select()
        except:
            pass

    def _wrap_command(self, func):
        if not func: return None
        def wrapper(*args, **kwargs):
            active_win = self.check_active_subwindow()
            if active_win:
                self._warn_and_restore_active_window(active_win)
                return "break"
            return func(*args, **kwargs)
        return wrapper

    def _initialize_tab_frames(self):
        self.tab_frames = {}
        for tab_name in ALL_TABS:
            frame = tk.Frame(self.notebook)
            self.notebook.add(frame, text=tab_name)
            self.tab_frames[tab_name] = frame

        self.bom_tab = self.tab_frames['BOM']

    def _create_all_ui(self):
        self._create_bom_ui()

    def _create_premium_button(self, parent, text, command, bg_color, fg_color="#ffffff", hover_bg=None, active_bg=None, font=("Segoe UI", 10, "bold"), anchor="w", padx=20):
        wrapped_command = self._wrap_command(command)
        if hover_bg is None:
            hover_bg = "#2B6CB0"
        if active_bg is None:
            active_bg = hover_bg
        
        btn = tk.Button(
            parent, 
            text=text, 
            command=wrapped_command,
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            font=font,
            height=2,
            bd=0,
            relief="flat",
            cursor="hand2",
            anchor=anchor,
            padx=padx
        )
        
        def on_enter(e):
            btn.config(bg=hover_bg)
        def on_leave(e):
            btn.config(bg=bg_color)
            
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn

    def _create_bom_ui(self):
        self.bom_tab.configure(bg="#EBF8FF")
        
        # Left Sidebar (Dark background, fixed width)
        left_col = tk.Frame(self.bom_tab, bg="#1A365D", width=440)
        left_col.pack(side="left", fill="both")
        left_col.pack_propagate(False)
        
        # Inner content for sidebar
        inner_content = tk.Frame(left_col, bg="#1A365D")
        inner_content.pack(fill="both", expand=True, padx=20, pady=30)
        
        # Right column (Logo - Light background)
        right_col = tk.Frame(self.bom_tab, bg="#EBF8FF")
        right_col.pack(side="right", expand=True, fill="both")
        
        tk.Label(inner_content, text="BOM OPERATIONS & MANAGEMENT", font=("Segoe UI", 10, "bold"), fg="#90CDF4", bg="#1A365D", anchor="w").pack(fill="x", pady=(15, 2))
        tk.Frame(inner_content, bg="#2B6CB0", height=1).pack(fill="x", pady=(0, 10))
        
        self.verify_bom_button = self._create_premium_button(
            inner_content, 
            text="1. BOM Verification", 
            command=lambda: verify_bom_workflow(self.window),
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.verify_bom_button.pack(fill="x", pady=5)
        
        self.assign_moq_button = self._create_premium_button(
            inner_content, 
            text="2. Assign MOQ", 
            command=lambda: assign_moq_workflow(self.window),
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.assign_moq_button.pack(fill="x", pady=5)

        self.input_target_price_button = self._create_premium_button(
            inner_content, 
            text="3. Input Target Price & EAU", 
            command=lambda: input_target_price_workflow(self.window),
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.input_target_price_button.pack(fill="x", pady=5)

        self.dispatch_rfq_button = self._create_premium_button(
            inner_content, 
            text="4. Dispatch RFQ", 
            command=lambda: dispatch_rfq_workflow(self.window),
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.dispatch_rfq_button.pack(fill="x", pady=5)
        
        tk.Label(inner_content, text="MASTER DATA MANAGEMENT", font=("Segoe UI", 10, "bold"), fg="#90CDF4", bg="#1A365D", anchor="w").pack(fill="x", pady=(15, 2))
        tk.Frame(inner_content, bg="#2B6CB0", height=1).pack(fill="x", pady=(0, 10))
        
        self.alt_mpn_maint_button = self._create_premium_button(
            inner_content, 
            text="Customer Alternative MPNs", 
            command=self.open_alt_mpn_maint,
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.alt_mpn_maint_button.pack(fill="x", pady=5)

        self.uom_maint_button = self._create_premium_button(
            inner_content, 
            text="Unit of Measurement (UOM) Conversion", 
            command=self.open_uom_conversion_maint,
            bg_color="#1A365D", 
            hover_bg="#2B6CB0",
            anchor="w"
        )
        self.uom_maint_button.pack(fill="x", pady=5)

        # --- PROJECT OVERVIEW ---
        tk.Label(inner_content, text="PROJECT OVERVIEW", font=("Segoe UI", 10, "bold"), fg="#90CDF4", bg="#1A365D", anchor="w").pack(fill="x", pady=(15, 2))
        tk.Frame(inner_content, bg="#2B6CB0", height=1).pack(fill="x", pady=(0, 10))

        self.pm_btn = self._create_premium_button(
            inner_content,
            text="📊 Project Management",
            command=self.open_pm_panel,
            bg_color="#1A365D",
            hover_bg="#2c3e6e",
            anchor="w"
        )
        self.pm_btn.pack(fill="x", pady=5)

        # Center/top logo in right column (Fixed size to prevent lag)
        logo_inner = tk.Frame(right_col, bg="#EBF8FF")
        logo_inner.pack(expand=True)
        
        self.logo_photo = None
        logo_path = None
        try:
            from utils import get_logo_path
            logo_path = get_logo_path("LOGO_PROFILE_DARK")
        except Exception:
            pass

        if logo_path and os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path)
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                w = 450
                h = int(w * img.height / img.width)
                img = img.resize((w, h), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading logo in BOM main app from {logo_path}: {e}")
                
        if self.logo_photo:
            logo_lbl = tk.Label(logo_inner, image=self.logo_photo, bg="#EBF8FF")
            logo_lbl.image = self.logo_photo
            logo_lbl.pack(pady=10)
        else:
            tk.Label(logo_inner, text="ContinuumX", font=("Segoe UI", 24, "bold"), fg="#1A365D", bg="#EBF8FF").pack()

        # Check if spawned by AI Agent for auto-verification, auto-dispatch, or auto-moq
        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
        payload_path = os.path.join(local_appdata, "ContXs", "agent_bom_payload.json")
        dispatch_cmd_path = os.path.join(local_appdata, "ContXs", "agent_dispatch_command.json")
        assign_moq_cmd_path = os.path.join(local_appdata, "ContXs", "agent_assign_moq_command.json")
        if os.path.exists(payload_path):
            self.window.after(300, lambda: verify_bom_workflow(self.window))
        elif os.path.exists(dispatch_cmd_path):
            try:
                os.remove(dispatch_cmd_path)
            except Exception:
                pass
            self.window.after(300, lambda: dispatch_rfq_workflow(self.window))
        elif os.path.exists(assign_moq_cmd_path):
            self.window.after(300, lambda: assign_moq_workflow(self.window))

    def open_pm_panel(self):
        try:
            from project_management_panel import open_project_management_panel
            from utils import BOM_DATA_DIR
            open_project_management_panel(self.window, BOM_DATA_DIR, module_name="BOM")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Project Management panel:\n{e}", parent=self.window)

    def open_alt_mpn_maint(self):
        if hasattr(self, 'alt_mpn_maint_instance') and self.alt_mpn_maint_instance is not None:
            try:
                if self.alt_mpn_maint_instance.winfo_exists():
                    self.alt_mpn_maint_instance.lift()
                    self.alt_mpn_maint_instance.focus_force()
                    return
            except tk.TclError:
                pass
                
        from sourcing_wizard import CustomerAlternativeMPNMaintenanceDialog
        self.alt_mpn_maint_instance = CustomerAlternativeMPNMaintenanceDialog(self.window)

    def open_uom_conversion_maint(self):
        if hasattr(self, 'uom_conv_maint_instance') and self.uom_conv_maint_instance is not None:
            try:
                if self.uom_conv_maint_instance.winfo_exists():
                    self.uom_conv_maint_instance.lift()
                    self.uom_conv_maint_instance.focus_force()
                    return
            except tk.TclError:
                pass
                
        from sourcing_wizard import UOMConversionMaintenanceDialog
        self.uom_conv_maint_instance = UOMConversionMaintenanceDialog(self.window)

    def _switch_login(self):
        from system_login import SystemLoginDialog
        login_dlg = SystemLoginDialog(self.window, stage_code="pending_bom", stage_name="BOM Verification")
        logged_user = login_dlg.show()
        if logged_user:
            self.user_name = logged_user
            self.window.user_name = logged_user
            self.window.title("Radysis BOM Management - " + logged_user + " (" + self.user_role + ")")
            self.login_btn.config(text=f"🔑 Switch User Login (Active User: {self.user_name})")
            messagebox.showinfo("Login Success", f"Switched active User login to: {logged_user}", parent=self.window)

    def _apply_role_restrictions(self):
        # Do not forget primary tab if it's the sole module tab for this microservice
        tabs_to_hide = ROLE_RESTRICTIONS.get(self.user_role, [])
        for tab_index in range(self.notebook.index("end") - 1, -1, -1):
            tab_name = self.notebook.tab(tab_index, "text")
            if tab_name in tabs_to_hide and self.user_role not in ("System Administrator", "Top Management", "Admin", "User", "Sourcing", "Engineering", "Viewer"):
                self.notebook.forget(tab_index)

# --- APPLICATION EXIT WRAPPER ---
def on_app_exit():
    def _do_exit():
        try:
            if root:
                root.quit()
                root.destroy()
        except:
            pass
        import os
        os._exit(0)
        
    try:
        if root:
            root.after(10, _do_exit)
            return
    except:
        pass
    import os
    os._exit(0)

if __name__ == "__main__":
    # Command line argument support: python main.py [username] [role]
    username = "admin"
    role = "Admin"
    if len(sys.argv) > 1:
        username = sys.argv[1]
    if len(sys.argv) > 2:
        role = sys.argv[2]
        
    root = tk.Tk()
    root.withdraw()
    
    main_app = MainApp(root, username, role, on_app_exit)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_app_exit()
