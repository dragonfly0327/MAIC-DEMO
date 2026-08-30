# Tkinter UI Standardization & Component Template (MPN/RPN Sourcing Suite)

This document defines the **Official UI/UX Design System and Reusable Component Reference** for the Sourcing Data Management application. Use this documentation as an initial setup prompt for any new window, tab, or program to immediately reproduce an identical, premium visual design and consistent user interaction model.

---

## 1. Global Window Setup & Styling Specifications


To maintain a premium, cohesive, and modern look across all windows (Toplevels, dialogs, and main views), adhere to the following rules:

### A. Color Palette
*   **Window Background**: `#EBF8FF` (Premium soft ice-blue background). This color is light, clean, and reduces eye strain compared to stark white.
*   **SAP-Style Title Accent Header**: `#dcedf5` (Light sky-blue banner background). Used as the background for title bars inside windows.
*   **Dark Accent Title**: `#1A365D` (Premium Dark Navy). Used for prominent section headers and titles.
*   **Warning Banner Background**: `#fff3cd` (Soft warm yellow). Used for warnings and important inline instructions.
*   **Warning Banner Foreground (Text)**: `#856404` (Dark gold-brown).
*   **Table Alternating Rows**:
    *   **Odd Rows**: `#ffffff` (Pure White)
    *   **Even Rows**: `#f0f4f8` (Very soft slate blue/white)
    *   **Separators / Dividers**: `#dcdcdc` (Light grey)
    *   **Blocked / Disabled Status Rows**: `#e0e0e0` (Neutral grey background)

### B. Typography & Fonts
Always use standard modern sans-serif typefaces (preferably **Segoe UI** on Windows, or **Arial** as a fallback):
*   **Main Header / Title**: `("Segoe UI", 14, "bold")` or `("Segoe UI", 16, "bold")`
*   **Section Categories**: `("Segoe UI", 11, "bold")`
*   **Regular Labels & Form Fields**: `("Segoe UI", 11)` or `("Arial", 10)`
*   **Data Entries & Inputs**: `("Segoe UI", 11)` or `("Arial", 10)`
*   **Status Indicators**: `("Arial", 9, "bold", "italic")`

### C. Standardized Button Styling (States & Colors)
To override standard grey Tkinter buttons, use these hex codes and configurations:

| Button Type | Background Code (`bg`) | Text Code (`fg`) | Active Background (`activebackground`) | Font Style | Relief & Border |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary / Action** (Save, OK, Confirm, Proceed, Add, Import, etc.) | **`#1A365D`** | `white` | **`#0077B6`** (Hover) / **`#2B71B9`** (Click) | `("Segoe UI", 10, "bold")` | `bd=0`, `relief="flat"`, `cursor="hand2"` |
| **Cancel / Neutral** (Cancel, Close, Revert, No, Logout, Skip, etc.) | **`#E2E8F0`** | **`#2D3748`** | **`#CBD5E0`** (Hover & Click) | `("Segoe UI", 10)` | `bd=0`, `relief="flat"`, `cursor="hand2"` |
| **Destructive / Alert** (Warnings, Overwrites) | **`#2ead4e`** (Green) | `white` | **`#248a3e`** | `("Arial", 9, "bold")` | `bd=0`, `relief="flat"`, `cursor="hand2"` |

*Padding Guidance*: Always use modern breathing room! Default buttons to `padx=15` and `pady=5`.

### D. Window Centering & Screen Autofit Logic
We support two screen sizing behaviors:
1.  **Developer Mode** (`AUTOFIT_TO_SCREEN = False`): Keeps windows at fixed size (e.g. `1200x700`) and centers them perfectly relative to the parent or screen. This is ideal if you are testing on a high-resolution widescreen monitor and don't want windows stretched excessively.
2.  **Deployment Mode** (`AUTOFIT_TO_SCREEN = True`): Automatically maximizes large main windows using the OS native maximize command (`self.state('zoomed')`) to perfectly fit the user's laptop screen. It keeps small dialogs/popups centered at their original sizes to keep them looking clean and professional.

To switch behaviors, toggle the `AUTOFIT_TO_SCREEN` global boolean at the top of `main.py`.

Here is the central intercepted monkeypatch setup in `main.py` that implements this dual behavior transparently across all windows:

```python
# --- Dynamic Auto-Centering Toplevel.geometry Monkeypatch ---
_orig_geometry = tk.Toplevel.geometry

def is_main_workspace(window):
    try:
        title = window.title()
        if "Login" in title or "Secure Login" in title:
            return False
            
        main_keywords = ["Radysis", "Sourcing Data", "Verification", "Assign MOQ", "Sourcing Master", "Currency & Markup"]
        for kw in main_keywords:
            if kw in title:
                return True
                
        # Geometry check (when mapped)
        geom = window.geometry()
        size_part = geom.split("+")[0]
        w = int(size_part.split("x")[0])
        if w >= 1100:
            return True
    except:
        pass
    return False

def patched_geometry(self, new_geometry=None):
    if new_geometry is None:
        return _orig_geometry(self)
        
    try:
        # Check if the geometry string is only size, e.g. "750x800"
        if "+" not in new_geometry and "-" not in new_geometry:
            w, h = map(int, new_geometry.split("x"))
            
            # Center on master or screen dynamically for this size!
            master = None
            try: master = self.master
            except: pass
            
            x, y = None, None
            # Only center relative to parent if the window is a small dialog (width < 1100)
            if w < 1100 and master and hasattr(master, 'winfo_viewable') and master.winfo_exists() and master.winfo_viewable() and master.winfo_width() > 1:
                try:
                    x = master.winfo_rootx() + (master.winfo_width() // 2) - (w // 2)
                    y = master.winfo_rooty() + (master.winfo_height() // 2) - (h // 2)
                except: pass
            
            if x is None or y is None:
                try:
                    screen_width = self.winfo_screenwidth()
                    screen_height = self.winfo_screenheight()
                    x = (screen_width // 2) - (w // 2)
                    y = (screen_height // 2) - (h // 2)
                except:
                    x, y = 100, 100
                    
            # Set the un-maximized centered boundary first (so the OS knows its default size is 1200x700)!
            _orig_geometry(self, f"{w}x{h}+{x}+{y}")
            
            # If dynamic screen fit mode is active, automatically maximize large windows
            if AUTOFIT_TO_SCREEN and (w >= 1100 or is_main_workspace(self)):
                try:
                    self.state('zoomed')
                except:
                    pass
            return
    except:
        pass
        
    return _orig_geometry(self, new_geometry)
```

### E. Main Window Stability & Modal Workflow Windows (Recommended)
To prevent visual flickering, stutters, or top-left "re-zooming" transitions when switching between screens, **do not hide/withdraw the main application window**. 

Instead, open workflow screens as **modal windows** layered on top of the main window. This keeps the main dashboard perfectly stable and maximized in the background.

To ensure that the workflow windows retain all native operating system title bar controls (such as the ability to **maximize/enlarge, minimize, and resize**), make them modal using `grab_set()`, but **do not make them transient to the parent** (since Windows OS automatically disables maximize/minimize buttons on transient Toplevels).

```python
# Recommended way to launch resizable workflow screens
wizard_window = tk.Toplevel(root)
wizard_window.title("BOM Verification Workflow")
wizard_window.geometry("1200x700")

# Keep main window stable and maximized in background
wizard_window.grab_set()  # Make it modal so the background is unclickable
```

#### Modal Minimize (-) Button Support
By default, calling Tcl/Tk's event-blocking `grab_set()` locks the event loop on Windows, which completely blocks native window manager commands (like clicking the native Minimize button `-` on the title bar). 

To solve this globally, `main.py` monkeypatches `grab_set()` and `grab_release()`. Instead of using Tcl/Tk's event-blocking mechanism, it uses Windows' native `-disabled` window attribute to disable all other visible windows in the application. This gives you 100% secure modal isolation while allowing the native Minimize (`-`), Maximize, and Close buttons on all workflow windows to work natively and flawlessly!
If a secondary window is explicitly hidden with `withdraw()` and then restored with `deiconify()`, Windows normally forgets the maximized state and restores it in a tiny default size. 

To handle this automatically as a fallback, `main.py` globally monkeypatches both `Toplevel` and `Tk` to re-maximize restored main windows when `AUTOFIT_TO_SCREEN = True`:

```python
# --- Deiconify Monkeypatch to prevent windows from shrinking after withdraw/restore ---
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
```

---

## 2. Reusable Component: View History Window

To prevent duplicate code, we have created a public, reusable **`StandardHistoryDialog`** class inside [ui_templates.py](file:///c:/Users/User/Downloads/MPNRPN_SourcingUI%20-%2020.04.2026%20-%2010.15PM/ui_templates.py). It creates a unified SAP-style change log view, groups changes visually, and handles all layout and color tags automatically.

### A. Dialog Code Structure (`ui_templates.py`)
```python
from ui_templates import StandardHistoryDialog
```

### B. Usage Instructions & Data Format
To open the change history for any record, simply call the class from your button action. The component expects a simple Python list of dictionaries:

```python
# 1. Define your history data (e.g. from JSON or database)
record_title = "MPN: 100nF-50V | Supplier: DigiKey"
history_log = [
    {
        "Date": "18.05.2026",
        "Time": "10:15:32 AM",
        "Changed By": "Admin",
        "Field Name": "Unit Price",
        "Old Value": "0.045",
        "New Value": "0.042"
    },
    {
        "Date": "18.05.2026",
        "Time": "10:15:32 AM",
        "Changed By": "Admin",
        "Field Name": "Stock",
        "Old Value": "5000",
        "New Value": "12000"
    },
    {
        "Date": "12.04.2026",
        "Time": "03:44:12 PM",
        "Changed By": "SourcingUser",
        "Field Name": "Record Created",
        "Old Value": "",
        "New Value": "Created via Excel Import"
    }
]

# 2. Instantiate and show the dialog in 1 line
StandardHistoryDialog(parent_window, record_title, history_log)
```

### C. Key Visual Features of the History Component
1.  **Header Accent Banner**: An elegant blue banner (`#dcedf5`) displays the title, giving the dialog a professional enterprise feel.
2.  **Alternating Table Rows**: Automatically styles lines using white (`#ffffff`) and soft blue-grey (`#f0f4f8`) tags.
3.  **Smart Date Separation**: Inspects dates sequentially. When the date changes, it inserts a grey divider bar (`#dcdcdc`) to group changes made on different days clearly.
4.  **Auto-Centering**: Dynamically calculates coordinates and locks mouse focus on itself (`grab_set`) to maintain application control.

---

## 3. Reusable Component: Multi-Value Filter Records Dialog

We have standardized the multi-value filtration system into the **`StandardFilterDialog`** class inside [ui_templates.py](file:///c:/Users/User/Downloads/MPNRPN_SourcingUI%20-%2020.04.2026%20-%2010.15PM/ui_templates.py). This dialog supports typing a single keyword directly into entry fields *or* clicking the multi-selection button (`⫘`) to input multiple search terms (one per line).

### A. How It Works
*   The developer provides a list of fields they want to filter.
*   The component builds the interface dynamically, maintaining all values.
*   When a user clicks `⫘`, a **`MultiValueInputDialog`** is launched, allowing bulk copy-pasting of search filters.
*   If multiple values are chosen, the box displays `<X values selected>` to indicate active bulk filtration.
*   On execution, the class returns a tidy dictionary of lists, which the developer can loop through.

### B. Usage Instructions (Standard Setup & Application)
Here is exactly how to integrate it in any window or database panel:

```python
from ui_templates import StandardFilterDialog

class MyCustomUI:
    def __init__(self, window):
        self.window = window
        
        # 1. Initialize filter dictionary mapping keys to lists
        self.active_filters = {
            "Part": [],
            "MPN": [],
            "MFR": [],
            "Supplier": []
        }
        
        # 2. Create the standard "Filter Records" trigger button
        self.btn_filter = tk.Button(self.window, text="🔍 Filter Records", command=self.open_filter)
        self.btn_filter.pack()

    def open_filter(self):
        # 3. Define fields configuration: (Key_Name, Display_Label)
        fields_config = [
            ("Part", "Part Number"),
            ("MPN", "Manufacturer MPN"),
            ("MFR", "Manufacturer Name"),
            ("Supplier", "Supplier")
        ]
        
        # 4. Open the dialog (Wait for close is managed automatically)
        dialog = StandardFilterDialog(
            master=self.window,
            title="Filter Records Database",
            fields_config=fields_config,
            initial_filters=self.active_filters
        )
        
        # 5. Check response
        if dialog.result is not None:
            self.active_filters = dialog.result
            self.apply_filtration_to_tree()

    def apply_filtration_to_tree(self):
        # 6. Apply filtration parameters dynamically in your loop
        f_part = [v.lower() for v in self.active_filters.get("Part", [])]
        f_mpn  = [v.lower() for v in self.active_filters.get("MPN", [])]
        f_mfr  = [v.lower() for v in self.active_filters.get("MFR", [])]
        f_supp = [v.lower() for v in self.active_filters.get("Supplier", [])]
        
        # Determine if any filter is active to highlight the filter button
        is_filtering = any([f_part, f_mpn, f_mfr, f_supp])
        if is_filtering:
            self.btn_filter.config(text="🔍 Filter Records (Active)", bg="#fffde7", fg="#856404")
        else:
            self.btn_filter.config(text="🔍 Filter Records", bg="#E2E8F0", fg="#2D3748")
            
        # Repopulate your Treeview
        # for row in database:
        #    if f_mpn and not any(term in str(row.MPN).lower() for term in f_mpn): continue
        #    if f_part and not any(term in str(row.Part).lower() for term in f_part): continue
        #    # ... insert into Treeview
```

---

## 4. Prompt Template for New Functions

Copy and paste this quick prompt block whenever you need to direct an AI to build a new window, ensuring perfect consistency with zero styling deviation:

```text
Please build a new Tkinter function window for [FUNCTION_NAME] using our standardized Sourcing UI design guidelines. 
Apply the following:
1. Set window bg to '#EBF8FF' and center it dynamically relative to parent.
2. Structure Title bar with a sky-blue accent background '#dcedf5' and Navy text '#1A365D'.
3. Color code buttons:
   - Primary Actions: Bg '#1A365D', Fg 'white', Hover bg '#0077B6', bold text, flat relief.
   - Cancel/Neutral Actions: Bg '#E2E8F0', Fg '#2D3748', Hover bg '#CBD5E0', flat relief.
4. Typography should default to 'Segoe UI' (Title 14 bold, fields 11).
5. For record change logs/auditing, import and instantiate ui_templates.StandardHistoryDialog.
6. For search/filter bars, import and instantiate ui_templates.StandardFilterDialog.
```

---
> [!NOTE]
> All standardized classes are physical, runnable components stored in the root workspace directory at [ui_templates.py](file:///c:/Users/User/Downloads/MPNRPN_SourcingUI%20-%2020.04.2026%20-%2010.15PM/ui_templates.py). When developing in any part of the project, simply import from this module to deploy history and filters in one line of code!
