import os
import json
import time
import uuid
from datetime import datetime

class ChatSessionStore:
    """
    Manages multi-session conversation persistence, history indexing,
    and 3-tier rolling context summarization for the ContinuumX AI Agent.
    """
    def __init__(self, base_storage_dir=None):
        if not base_storage_dir:
            local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            base_storage_dir = os.path.join(local_app, "ContXs", "chat_sessions")
        
        self.storage_dir = base_storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_session_path(self, session_id):
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.storage_dir, f"session_{safe_id}.json")

    def create_new_session(self, initial_title="New Conversation"):
        session_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_data = {
            "session_id": session_id,
            "title": initial_title,
            "created_at": now_iso,
            "last_updated": now_iso,
            "messages": [],
            "active_rfq_json": None,
            "summary_context": ""
        }
        self.save_session(session_id, session_data)
        return session_id, session_data

    def save_session(self, session_id, session_data):
        if not session_id or not isinstance(session_data, dict):
            return False
        
        session_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fp = self._get_session_path(session_id)
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ChatSessionStore] Error saving session {session_id}: {e}")
            return False

    def load_session(self, session_id):
        fp = self._get_session_path(session_id)
        if not os.path.exists(fp):
            return None
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChatSessionStore] Error loading session {session_id}: {e}")
            return None

    def list_sessions(self):
        """Returns all sessions sorted by last updated descending."""
        sessions = []
        if not os.path.exists(self.storage_dir):
            return sessions
        
        for f in os.listdir(self.storage_dir):
            if f.startswith("session_") and f.endswith(".json"):
                fp = os.path.join(self.storage_dir, f)
                try:
                    with open(fp, "r", encoding="utf-8") as s_file:
                        data = json.load(s_file)
                        sessions.append({
                            "session_id": data.get("session_id", f[8:-5]),
                            "title": data.get("title", "Untitled Conversation"),
                            "created_at": data.get("created_at", ""),
                            "last_updated": data.get("last_updated", ""),
                            "msg_count": len(data.get("messages", [])),
                            "has_rfq": bool(data.get("active_rfq_json"))
                        })
                except Exception:
                    continue

        sessions.sort(key=lambda s: s.get("last_updated", ""), reverse=True)
        return sessions

    def delete_session(self, session_id):
        fp = self._get_session_path(session_id)
        if os.path.exists(fp):
            try:
                os.remove(fp)
                return True
            except Exception as e:
                print(f"[ChatSessionStore] Error deleting session {session_id}: {e}")
                return False
        return False

    def clear_all_sessions(self):
        if not os.path.exists(self.storage_dir):
            return 0
        deleted = 0
        for f in os.listdir(self.storage_dir):
            if f.startswith("session_") and f.endswith(".json"):
                try:
                    os.remove(os.path.join(self.storage_dir, f))
                    deleted += 1
                except Exception:
                    pass
        return deleted

    def get_rolling_context(self, messages, max_recent=6):
        """
        Extracts active working memory without blowing LLM context tokens.
        Keeps the last `max_recent` messages in full, while summarizing older turns.
        """
        if not messages:
            return ""
        
        if len(messages) <= max_recent:
            compact_lines = []
            for m in messages:
                role = "User" if m.get("sender") == "user" else "Assistant"
                text = str(m.get("text", "")).strip()
                if text:
                    compact_lines.append(f"{role}: {text[:300]}")
            return "\n".join(compact_lines)
        
        # Summarize older messages
        older = messages[:-max_recent]
        recent = messages[-max_recent:]
        
        summary_points = []
        for m in older:
            if m.get("sender") == "user":
                t = str(m.get("text", ""))[:120]
                summary_points.append(f"- Discussed: {t}")
        
        rolling_block = f"Prior Conversation Summary:\n" + "\n".join(summary_points[:5]) + "\n\nRecent Turns:\n"
        for m in recent:
            role = "User" if m.get("sender") == "user" else "Assistant"
            text = str(m.get("text", "")).strip()
            if text:
                rolling_block += f"{role}: {text[:300]}\n"
        
        return rolling_block
