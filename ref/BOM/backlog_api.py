import os
import json
import time
from datetime import datetime
import sys
import configparser

# Resolve base project directory (supporting PyInstaller and Nuitka compiled paths)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load configuration
config = configparser.ConfigParser()
config_file = os.path.join(BASE_DIR, "config.ini")
if os.path.exists(config_file):
    try:
        config.read(config_file, encoding='utf-8')
    except Exception as e:
        print(f"Error reading config file: {e}")

# Resolve MASTER_BACKLOG_DIR strictly from config.ini
if not config.has_option('PATHS', 'MASTER_BACKLOG_DIR'):
    raise KeyError("Configuration Error: 'MASTER_BACKLOG_DIR' is not configured under '[PATHS]' in config.ini.")

val = config.get('PATHS', 'MASTER_BACKLOG_DIR').strip()
if not val:
    raise ValueError("Configuration Error: 'MASTER_BACKLOG_DIR' option under '[PATHS]' in config.ini is empty.")

MASTER_BACKLOG_DIR = os.path.normpath(val.replace('\\', '/'))


def log_backlog_event(event_type, app_name, user_name, details):
    """
    Logs an event to the centralized event backlog.
    Records a JSON log line to master_backlog_events.jsonl.
    Also appends a human-readable entry to a master_backlog_log.txt file.
    """
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "app_name": app_name,
        "user_name": user_name,
        "details": details
    }
    
    if not os.path.exists(MASTER_BACKLOG_DIR):
        try:
            os.makedirs(MASTER_BACKLOG_DIR)
        except Exception:
            pass
            
    # Write to master_backlog_events.jsonl
    jsonl_path = os.path.join(MASTER_BACKLOG_DIR, "master_backlog_events.jsonl")
    for attempt in range(5):
        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            break
        except IOError:
            time.sleep(0.1)
            
    # Also write a human-readable text entry to master_backlog_log.txt
    txt_path = os.path.join(MASTER_BACKLOG_DIR, "master_backlog_log.txt")
    timestamp_str = event["timestamp"]
    
    detail_lines = []
    for k, v in details.items():
        detail_lines.append(f"  {k}: {v}")
    details_str = "\n".join(detail_lines)
    
    log_entry = (
        f"=================================================================\n"
        f"[{timestamp_str}] EVENT: {event_type}\n"
        f"App: {app_name} | User: {user_name}\n"
        f"Details:\n{details_str}\n"
        f"=================================================================\n\n"
    )
    
    for attempt in range(5):
        try:
            with open(txt_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
            break
        except IOError:
            time.sleep(0.1)
