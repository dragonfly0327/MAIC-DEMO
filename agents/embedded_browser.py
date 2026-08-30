"""
Single-Instance Docked Web Browser Manager for ContinuumX Platform.
Manages a unified, single-window or tabbed web browser interface.
Ensures clicking different suppliers (Google, Mouser, DigiKey, Octopart)
NEVER creates scattered multiple pop-up windows.
"""

import sys
import subprocess
import os
import threading
import time

class SingleWindowWebManager:
    _instance_process = None
    _command_file = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ContXs", "browser_command.txt")

    @classmethod
    def navigate_or_open(cls, url, title="Component Web Sourcing"):
        """
        Navigates the existing browser window or launches a single unified window.
        Prevents multiple popup windows from scattering across the user's screen.
        """
        # Ensure ContXs directory exists
        os.makedirs(os.path.dirname(cls._command_file), exist_ok=True)
        
        # Write the target URL to the command file for the running browser to poll
        try:
            with open(cls._command_file, "w", encoding="utf-8") as f:
                f.write(f"{title}:::{url}")
        except Exception:
            pass

        # Check if process is already running
        if cls._instance_process is not None and cls._instance_process.poll() is None:
            # Process is alive, it will pick up the new URL via command file
            return True

        # Launch single unified browser script
        python_exe = sys.executable
        runner_script = f"""
import webview
import time
import os
import threading

cmd_file = r'{cls._command_file}'
current_url = r'{url}'
current_title = r'{title}'
window = None

def poll_url_updates():
    last_val = ''
    while True:
        try:
            if os.path.exists(cmd_file):
                with open(cmd_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content and content != last_val:
                    last_val = content
                    parts = content.split(':::', 1)
                    if len(parts) == 2:
                        new_t, new_u = parts
                    else:
                        new_u = parts[0]
                        new_t = 'Component Sourcing'
                    if window and new_u:
                        window.load_url(new_u)
                        window.set_title(new_t)
        except Exception:
            pass
        time.sleep(0.4)

def run():
    global window
    window = webview.create_window(
        current_title,
        current_url,
        width=1180,
        height=820,
        resizable=True
    )
    t = threading.Thread(target=poll_url_updates, daemon=True)
    t.start()
    webview.start()

if __name__ == '__main__':
    run()
"""
        try:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            cls._instance_process = subprocess.Popen(
                [python_exe, "-c", runner_script],
                creationflags=flags,
                close_fds=True
            )
            return True
        except Exception as ex:
            print(f"[SingleWindowWebManager] Launch error: {ex}")
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
            return False

def launch_in_app_browser(url, title="Component Web Sourcing"):
    return SingleWindowWebManager.navigate_or_open(url, title)

if __name__ == "__main__":
    test_u = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    launch_in_app_browser(test_u, "Test Browser")
