# ==============================================================================
# --- ContinuumX Evidence Schema ---
# Shared data contract for all RFQ extraction agents.
# Defines ResolutionType, make_evidence factory, and ConflictCandidate.
# Eliminates duplicate definitions across drawing_agent and multimodal_extractor.
# ==============================================================================


class ResolutionType:
    """Classification of how a field value was determined."""
    DIRECT = "DIRECT"
    DERIVED_INFERRED = "DERIVED_INFERRED"
    MASTER_RESOLVED = "MASTER_RESOLVED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


def make_evidence(
    value,
    res_type: str,
    source_doc: str,
    page: int = 1,
    zone: str = "",
    snippet: str = "",
    reasoning: str = "",
    confidence: float = 0.95
) -> dict:
    """
    Factory for a standardized evidence tracking dictionary.
    Zero-Hallucination Policy: if value is absent, use value=None and NOT_AVAILABLE.
    """
    if res_type == ResolutionType.NOT_AVAILABLE:
        value = None
        confidence = 0.0

    return {
        "value": value,
        "resolution_type": res_type,
        "source_document": source_doc,
        "page": page,
        "source_zone": zone,
        "raw_evidence_snippet": str(snippet).strip()[:250] if snippet else "",
        "reasoning": reasoning,
        "confidence": round(float(confidence), 4)
    }


class ConflictCandidate:
    """
    Records a detected conflict between two sources for the same field.
    Used for human review in the Evidence Audit UI Conflicts tab.
    """
    def __init__(self, field: str, source_a: dict, source_b: dict,
                 auto_resolution: str = "NEEDS_HUMAN", auto_reasoning: str = ""):
        self.field = field
        self.source_a = source_a
        self.source_b = source_b
        self.auto_resolution = auto_resolution
        self.auto_reasoning = auto_reasoning

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "source_a": self.source_a,
            "source_b": self.source_b,
            "auto_resolution": self.auto_resolution,
            "auto_reasoning": self.auto_reasoning
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConflictCandidate":
        return cls(
            field=d.get("field", ""),
            source_a=d.get("source_a", {}),
            source_b=d.get("source_b", {}),
            auto_resolution=d.get("auto_resolution", "NEEDS_HUMAN"),
            auto_reasoning=d.get("auto_reasoning", "")
        )

    def __repr__(self):
        a_val = self.source_a.get("value", "?")
        b_val = self.source_b.get("value", "?")
        return f"ConflictCandidate(field={self.field!r}, A={a_val!r} vs B={b_val!r}, res={self.auto_resolution})"
