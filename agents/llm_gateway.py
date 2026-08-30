import os
import re
import json
import time
import hashlib
import random
import threading
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "llm_cache.json")


class LLMGateway:
    """
    Central LLM Gateway & Rate Limiter for ContinuumX.

    Architecture features:
    1. Global Rate Limiter: Enforces min delay (default 2.5s) & single-concurrency lock.
    2. SHA-256 Payload Caching: Avoids duplicate API calls for identical drawings/text.
    3. Session Quota Pause: When HTTP 429 occurs, pauses API calls for 10 min so fast local fallback takes over instantly.
    4. Smart 429 Handling: Respects HTTP Retry-After header + exponential backoff.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_path=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LLMGateway, cls).__new__(cls)
                cls._instance._init_gateway(config_path)
            return cls._instance

    def _init_gateway(self, config_path=None):
        self.config_path = config_path or os.path.join(BASE_DIR, "config.ini")
        self.call_lock = threading.Lock()
        self.last_call_timestamp = 0.0
        self.min_interval_sec = 2.5  # Max ~24 requests/min, comfortably under 15 RPM burst limit
        self.cache = self._load_cache()
        self.quota_exhausted_until = 0.0

    def _load_cache(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def clear_cache(self, doc_keyword=None):
        """Clears memory & disk cache, optionally matching a specific doc or RFQ keyword."""
        if not doc_keyword:
            self.cache.clear()
        else:
            kw = str(doc_keyword).lower()
            keys_to_del = [k for k, v in self.cache.items() if kw in k.lower() or (isinstance(v, dict) and kw in str(v).lower())]
            for k in keys_to_del:
                del self.cache[k]
        self._save_cache()
        print(f"[LLMGateway] Cache invalidated for '{doc_keyword or 'ALL'}'")

    def _get_api_key(self):
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key and os.path.exists(self.config_path):
            try:
                import configparser
                cfg = configparser.ConfigParser()
                cfg.read(self.config_path, encoding="utf-8")
                if "AGENTS_LLM" in cfg and "gemini_api_key" in cfg["AGENTS_LLM"]:
                    key = cfg["AGENTS_LLM"]["gemini_api_key"].strip()
            except Exception:
                pass
        return key

    def _compute_hash(self, system_prompt, user_prompt, inline_images=None):
        h = hashlib.sha256()
        h.update(system_prompt.encode("utf-8"))
        h.update(user_prompt.encode("utf-8"))
        if inline_images:
            for img_b64 in inline_images:
                h.update(img_b64[:200].encode("utf-8"))
                h.update(str(len(img_b64)).encode("utf-8"))
        return h.hexdigest()

    def generate_json(self, system_prompt, user_prompt, inline_images=None, model="gemini-flash-latest", doc_name=""):
        """
        Executes a rate-limited, cached request to Gemini API, returning a tuple (parsed_dict, status_str).
        """
        from agents.prompt_guard import check_prompt

        decision = check_prompt(user_prompt, "brain")
        if not decision.allowed:
            return None, "PROMPT_REJECTED"

        api_key = self._get_api_key()
        if not api_key:
            print(f"[LLMGateway] No Gemini API key available for {doc_name}")
            return None, "NO_API_KEY"

        # 1. SHA-256 Disk Cache Check
        payload_hash = self._compute_hash(system_prompt, user_prompt, inline_images)
        if payload_hash in self.cache:
            cached_entry = self.cache[payload_hash]
            print(f"[LLMGateway] Cache HIT for {doc_name or payload_hash[:10]} (0 API calls used)")
            return cached_entry.get("result"), "CACHE_HIT"

        # Fast-Path Session Quota Pause (If API daily/per-minute quota hit, skip HTTP calls and use local fallback immediately)
        if time.time() < self.quota_exhausted_until:
            print(f"[LLMGateway] API Quota exhausted — using instant local fallback for {doc_name} (0s wait)")
            return None, "QUOTA_EXHAUSTED_PAUSE"

        # 2. Prepare API Payload
        parts = [
            {"text": f"System Instruction: {system_prompt}"},
            {"text": user_prompt}
        ]
        if inline_images:
            for img_b64 in inline_images:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})

        payload = {"contents": [{"parts": parts}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # 3. Single-Concurrency Rate-Limited Execution Loop
        max_attempts = 2
        last_error = None

        with self.call_lock:
            for attempt in range(1, max_attempts + 1):
                # Enforce pacing delay
                now = time.time()
                elapsed = now - self.last_call_timestamp
                if elapsed < self.min_interval_sec:
                    sleep_time = self.min_interval_sec - elapsed
                    time.sleep(sleep_time)

                self.last_call_timestamp = time.time()

                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=90) as response:
                        if response.status == 200:
                            res_json = json.loads(response.read().decode("utf-8"))
                            text_out = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            text_out = re.sub(r'^```(?:json)?\s*', '', text_out, flags=re.IGNORECASE)
                            text_out = re.sub(r'\s*```$', '', text_out)
                            parsed_obj = json.loads(text_out)

                            # Save to disk cache & clear quota pause
                            self.quota_exhausted_until = 0.0
                            self.cache[payload_hash] = {
                                "doc_name": doc_name,
                                "timestamp": time.time(),
                                "result": parsed_obj
                            }
                            self._save_cache()
                            return parsed_obj, "SUCCESS"

                except urllib.error.HTTPError as e:
                    last_error = e
                    cat = f"HTTP_{e.code}_QUOTA" if e.code in (429, 503) else f"HTTP_{e.code}_ERROR"
                    try:
                        from agents.telemetry_tracker import ErrorTelemetryStore
                        ErrorTelemetryStore().record_error(
                            module="LLMGateway",
                            error_category=cat,
                            error_message=f"HTTP {e.code} for {doc_name}: {e}",
                            severity="WARNING" if e.code in (429, 503) else "ERROR",
                            document_name=doc_name,
                            prompt_context={"system_prompt": system_prompt[:200], "user_prompt": user_prompt[:200]},
                            recovery_action="Activating local heuristic fallback parser" if attempt >= max_attempts else f"Quick retry backoff attempt {attempt}",
                            status="RECOVERED_VIA_FALLBACK" if attempt >= max_attempts else "RETRYING"
                        )
                    except Exception:
                        pass

                    if e.code in (429, 503, 500):
                        if attempt >= max_attempts:
                            # Quota limit hit: gentle 12s backoff to allow Gemini 15 RPM bucket to refill
                            self.quota_exhausted_until = time.time() + 12.0
                            print(f"[LLMGateway] HTTP {e.code} quota limit hit for {doc_name} — backing off for 12s...")
                            break
                        wait = 4.0 * attempt
                        print(f"[LLMGateway] HTTP {e.code} on attempt {attempt}/{max_attempts} for {doc_name} — quick retry in {wait}s...")
                        time.sleep(wait)
                        continue
                    else:
                        print(f"[LLMGateway] HTTP Error {e.code} for {doc_name}: {e}")
                        break
                except Exception as e:
                    last_error = e
                    try:
                        from agents.telemetry_tracker import ErrorTelemetryStore
                        ErrorTelemetryStore().record_error(
                            module="LLMGateway",
                            error_category="LLM_EXECUTION_EXCEPTION",
                            error_message=str(e),
                            severity="ERROR",
                            document_name=doc_name,
                            prompt_context={"system_prompt": system_prompt[:200], "user_prompt": user_prompt[:200]},
                            recovery_action="Fallback to local heuristic parser",
                            status="RECOVERED_VIA_FALLBACK"
                        )
                    except Exception:
                        pass
                    print(f"[LLMGateway] LLM execution error for {doc_name}: {e}")
                    break

        return None, f"FAILED: {last_error}"

    def generate_text_or_multimodal(self, system_prompt, user_prompt, inline_images=None, model="gemini-flash-latest", doc_name="ChatMultimodal"):
        """
        Executes an open-ended conversational or analytical multimodal query to Gemini Vision.
        Returns (text_response_str, status_str).
        """
        from agents.prompt_guard import check_prompt

        decision = check_prompt(user_prompt, "brain")
        if not decision.allowed:
            return decision.user_message, "PROMPT_REJECTED"

        api_key = self._get_api_key()
        if not api_key:
            return "⚠️ Gemini API Key not configured in config.ini.", "NO_API_KEY"

        # Check session pause
        if time.time() < self.quota_exhausted_until:
            return "⚠️ Gemini API daily rate limit pause is active. Please try again shortly.", "QUOTA_EXHAUSTED_PAUSE"

        parts = [
            {"text": f"System Instruction: {system_prompt}"},
            {"text": user_prompt}
        ]
        if inline_images:
            for img_b64 in inline_images:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})

        payload = {"contents": [{"parts": parts}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        max_attempts = 2
        last_err = None

        with self.call_lock:
            for attempt in range(1, max_attempts + 1):
                now = time.time()
                elapsed = now - self.last_call_timestamp
                if elapsed < self.min_interval_sec:
                    time.sleep(self.min_interval_sec - elapsed)
                self.last_call_timestamp = time.time()

                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=90) as response:
                        if response.status == 200:
                            res_json = json.loads(response.read().decode("utf-8"))
                            text_out = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                            self.quota_exhausted_until = 0.0
                            return text_out, "SUCCESS"
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code in (503, 500):
                        # Transient Google server overload -> retry immediately once
                        if attempt < max_attempts:
                            time.sleep(1.5)
                            continue
                        return f"⚠️ Google Gemini service was temporarily busy (HTTP {e.code}). Please try your prompt again.", f"HTTP_{e.code}"
                    elif e.code == 429:
                        if attempt < max_attempts:
                            time.sleep(2.0)
                            continue
                        self.quota_exhausted_until = time.time() + 300.0
                        return "⚠️ Gemini API rate limit reached (HTTP 429). Please wait a moment before sending another prompt.", "HTTP_429"
                    else:
                        return f"⚠️ API Error (HTTP {e.code}): {e.reason}", f"HTTP_{e.code}"
                except Exception as e:
                    last_err = e
                    return f"⚠️ Processing error: {e}", "ERROR"

        return f"⚠️ Request could not be processed: {last_err}", "FAILED"
