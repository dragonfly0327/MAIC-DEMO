# -*- coding: utf-8 -*-
"""Central inbound prompt rejection for ContinuumX chat and LLM calls.

Chatboxes must not implement their own jailbreak filters. Every LLM path
(BrainRouter.query_model, LLMGateway) calls check_prompt() here first.
"""

from __future__ import annotations

import os
import re
import sys
import configparser
from dataclasses import dataclass

if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS") or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif "__file__" in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != "-c":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    BASE_DIR = os.getcwd()


# Zero-width / bidi marks used to hide jailbreak text from naive filters.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_LEET = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s",
})

INJECTION_RULES = [
    # Instruction override
    ("inject_ignore_previous", r"ignore\s+(all\s+)?(previous|prior|above|your|earlier|existing)\s+(instructions?|prompts?|rules?|guidelines?|policies)"),
    ("inject_disregard_rules", r"\b(disregard|forget|override|discard|skip)\s+(all\s+)?(your\s+)?(previous|prior|system|safety|content)?\s*(instructions?|rules?|guidelines?|guardrails?|filters?)\b"),
    ("inject_from_now_on", r"\bfrom\s+now\s+on\s+you\s+(will|must|should)\s+(ignore|disregard|have no|be unrestricted|jailbreak)"),
    ("inject_new_instructions", r"\b(new|updated)\s+system\s+(instructions?|prompt)\s*[:=]"),
    ("inject_do_not_follow", r"\bdo\s+not\s+follow\s+(your\s+)?(original|previous|system)\s+(instructions?|rules?)\b"),
    ("inject_reset_persona", r"\b(reset|clear|wipe)\s+(your\s+)?(instructions?|memory|persona|system\s+prompt)\b"),
    # Jailbreak personas / modes
    ("inject_jailbreak", r"\b(jailbreak|jail\s*break|you are now dan|do anything now|dan mode|developer mode|god mode|evil mode|uncensored mode)\b"),
    ("inject_no_restrictions", r"\b(no\s+restrictions?|without\s+(any\s+)?(restrictions?|limits?|guardrails?|filters?)|unfiltered\s+mode|uncensored\s+mode)\b"),
    ("inject_pretend_unrestricted", r"\b(pretend|act as if|roleplay as if)\s+you\s+(have\s+)?no\s+(rules?|restrictions?|limits?|ethics)\b"),
    ("inject_disable_safety", r"\b(disable|turn off|remove|bypass)\s+(the\s+)?(safety|content)?\s*(filter|guardrail|moderation|alignment)\b"),
    ("inject_opposite_mode", r"\b(opposite\s+mode|anti-?gpt|aim\s+mode|stan\s+mode|dude\s+mode)\b"),
    ("inject_sudo", r"\b(sudo\s+mode|admin\s+override|root\s+access|enable\s+developer\s+commands)\b"),
    # System prompt / hidden instruction extraction
    ("inject_system_prompt", r"\b(reveal|show|print|repeat|output|dump|display|quote)\s+(your\s+)?(full\s+)?(system\s+prompt|hidden\s+instructions?|initial\s+prompt|developer\s+message|policy\s+prompt)\b"),
    ("inject_what_instructions", r"\b(what|list|repeat)\s+(are\s+)?(your|the)\s+(hidden|system|developer|internal)\s+(instructions?|rules?|guidelines?|prompt)\b"),
    ("inject_everything_above", r"\b(repeat|print|output)\s+(everything|all)\s+(above|before this)\b"),
    ("inject_begin_with_prompt", r"\b(start|begin)\s+(your\s+)?(answer|reply|response)\s+with\s+(your\s+)?system\s+prompt\b"),
    # Delimiter / role hijack
    ("inject_xml_system", r"<\s*(system|assistant|instruction|im_start)\b"),
    ("inject_chatml", r"<\|im_start\|>|<\|system\|>|\[INST\]|\[/INST\]"),
    ("inject_role_system", r"\brole\s*[:=]\s*['\"]?system['\"]?"),
    ("inject_markdown_system", r"(?m)^\s*(system|developer)\s*:\s+"),
    ("inject_hash_instruction", r"###\s*(system|instruction|developer)\b"),
    # Secrets / credentials
    ("inject_dump_secrets", r"\b(dump|reveal|print|show|exfiltrate|leak)\s+(the\s+)?(api\s*keys?|secrets?|passwords?|credentials?|tokens?|encryption\s+keys?)\b"),
    ("inject_ask_secret", r"\b(what('?s| is)|give me|tell me|send me)\s+(the\s+)?((gemini|openai|google)\s+)?(api\s*keys?|passwords?|secrets?|auth(entication)?\s+tokens?|cx_agent_auth_token)\b"),
    ("inject_env_secrets", r"\b(print|show|cat|dump)\s+(.{0,20})?(\.env|config\.ini|environment\s+variables?)\b"),
    ("inject_bearer", r"\b(bearer\s+token|authorization:\s*bearer)\b"),
    # Domain policy bypass (avoid "bypass capacitor")
    ("inject_bypass_policy", r"\bbypass\s+(the\s+)?(markup|moq|pricing|costing|corporate|approval|hitl|safety)\s*(policy|rules?|margin|gate|check)?\b"),
    ("inject_skip_approval", r"\b(skip|avoid|circumvent)\s+(the\s+)?(human\s+)?(approval|hitl|review\s+gate|operator\s+check)\b"),
    ("inject_zero_margin", r"\b(set|force|make)\s+(margin|markup)\s+(to\s+)?(zero|0%|0\s*percent)\b"),
    ("inject_waive_nre", r"\b(waive|remove|ignore)\s+(the\s+)?nre\b"),
    # Encoding / indirect injection
    ("inject_base64_exec", r"\b(decode|base64)\b.{0,40}\b(execute|run|follow|instructions?)\b"),
    ("inject_translate_then", r"\b(translate|decode)\b.{0,30}\bthen\s+(execute|follow|ignore\s+previous)\b"),
    ("inject_educational_jailbreak", r"\b(for\s+(educational|research)\s+purposes).{0,40}\b(jailbreak|bypass\s+safety|ignore\s+instructions)\b"),
    ("inject_hypothetical_unrestricted", r"\bin a hypothetical world\b.{0,40}\bno\s+(rules?|restrictions?)\b"),
    # Tool / code execution
    ("inject_shell", r"\b(os\.system|subprocess\.|popen\s*\(|eval\s*\(|exec\s*\(|__import__\s*\()\b"),
    ("inject_sql", r"\b(union\s+select|drop\s+table|or\s+1\s*=\s*1|;--)\b"),
    ("inject_path_traversal", r"(\.\./|\.\.\\|etc/passwd|windows\\system32)"),
    ("inject_exfil_url", r"\b(curl|wget|invoke-webrequest)\b.{0,40}\b(api[_-]?key|password|token|secret)\b"),
    ("inject_exfil_webhook", r"\b(send|post|upload)\s+(this|the\s+data|secrets?|keys?)\s+(to|via)\s+(https?://|a\s+webhook)\b"),
    # Social engineering
    ("inject_dev_override", r"\b(i am (the )?(developer|admin|sysadmin|owner)|this is (an? )?(authorized )?override)\b.{0,40}\b(ignore|disable|bypass)\b"),
    ("inject_it_test", r"\b(security test|penetration test|red team)\b.{0,40}\b(disable (the )?filter|ignore instructions|jailbreak)\b"),
    ("inject_grandmother", r"\b(my grandmother used to|for my dying grandmother)\b.{0,40}\b(system prompt|api key|password)\b"),
]


# Off-scope mutations: costing/npi/wi/sourcing must not rewrite BOM; bom must not change costing.
CROSS_MODULE_DENY = {
    "costing": ("bom_scope", r"\b(import\s+(customer\s+)?bom|column\s+mapping|assign\s+moqs?|verify\s+bom|rewrite\s+bom)\b"),
    "npi": ("bom_scope", r"\b(import\s+(customer\s+)?bom|assign\s+moqs?|rewrite\s+bom)\b"),
    "wi": ("bom_scope", r"\b(import\s+(customer\s+)?bom|assign\s+moqs?|rewrite\s+bom)\b"),
    "sourcing": ("bom_scope", r"\b(import\s+(customer\s+)?bom|column\s+mapping|rewrite\s+bom)\b"),
    "bom": ("costing_scope", r"\b(apply\s+(target\s+)?margin|change\s+markup|bypass\s+markup|set\s+selling\s+price)\b"),
    "cycletime": ("costing_scope", r"\b(apply\s+(target\s+)?margin|change\s+markup|bypass\s+markup)\b"),
}


def _normalize_for_match(text: str) -> str:
    """Strip obfuscation so hidden jailbreak text still matches."""
    cleaned = _INVISIBLE.sub("", str(text or ""))
    cleaned = cleaned.replace("\x00", "")
    cleaned = re.sub(r"[\u00a0\u3000]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.translate(_LEET)


@dataclass
class PromptDecision:
    allowed: bool
    rule_id: str = ""
    user_message: str = ""
    module_key: str = ""

    def log_rejection(self) -> None:
        if self.allowed:
            return
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        try:
            from agents.telemetry_tracker import ErrorTelemetryStore

            ErrorTelemetryStore().record_error(
                module="PromptGuard",
                error_category="PROMPT_REJECTED",
                error_message=f"Rejected by rule {self.rule_id} (module={self.module_key})",
                severity="WARNING",
                prompt_context={"rule_id": self.rule_id, "module": self.module_key},
                recovery_action="Prompt blocked before LLM call",
                status="BLOCKED",
            )
        except Exception:
            pass


class PromptGuard:
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(BASE_DIR, "config.ini")
        self.config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            try:
                self.config.read(self.config_path, encoding="utf-8")
            except Exception:
                pass

    def check(self, prompt: str, module_key: str = "brain") -> PromptDecision:
        raw = str(prompt or "")
        if not raw.strip():
            return PromptDecision(allowed=True, module_key=module_key)

        module = (module_key or "brain").lower().replace(" ", "")
        text = _normalize_for_match(raw)
        for rule_id, pattern in INJECTION_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                return self._reject(
                    rule_id,
                    module,
                    "This request was blocked by ContinuumX prompt policy "
                    f"({rule_id}). Rephrase without jailbreak or secret-extraction language.",
                )

        extra_deny = []
        if "PROMPT_GUARD" in self.config:
            extra = self.config["PROMPT_GUARD"].get("global_deny", "").strip()
            if extra:
                extra_deny = [p.strip() for p in extra.split(",") if p.strip()]
        lowered = text.lower()
        for phrase in extra_deny:
            if phrase.lower() in lowered:
                return self._reject(
                    "config_global_deny",
                    module,
                    "This request was blocked by ContinuumX prompt policy.",
                )

        if module != "brain" and module in CROSS_MODULE_DENY:
            rule_id, pattern = CROSS_MODULE_DENY[module]
            if re.search(pattern, text, re.IGNORECASE):
                return self._reject(
                    rule_id,
                    module,
                    f"This request is outside the {module} module scope. "
                    "Use the Brain assistant or the owning module instead.",
                )

        allow_key = f"{module}_allow"
        if module != "brain" and "PROMPT_GUARD" in self.config:
            allow = self.config["PROMPT_GUARD"].get(allow_key, "").strip()
            tokens = [t.strip().lower() for t in allow.split(",") if t.strip()]
            if tokens:
                if not any(tok in lowered for tok in tokens):
                    if re.search(r"\b(import|assign|dispatch|calculate|override|delete|rewrite)\b", lowered):
                        return self._reject(
                            "module_allowlist",
                            module,
                            f"This request is outside {module} scope.",
                        )

        return PromptDecision(allowed=True, module_key=module)

    def _reject(self, rule_id: str, module: str, user_message: str) -> PromptDecision:
        decision = PromptDecision(
            allowed=False,
            rule_id=rule_id,
            module_key=module,
            user_message=user_message,
        )
        decision.log_rejection()
        return decision


def check_prompt(prompt: str, module_key: str = "brain") -> PromptDecision:
    return PromptGuard().check(prompt, module_key)
