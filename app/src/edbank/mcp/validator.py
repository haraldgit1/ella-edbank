"""
Validates LLM tool-call requests before forwarding to MCP.
All validation errors are returned as strings (not raised) so the caller
can feed them back to the model for one corrective round.
"""
import re

_ALLOWED_TOOLS = {"get_bank_accounts_by_person_name"}
_MIN_NAME_LEN = 2
_MAX_NAME_LEN = 200
_SUSPICIOUS_PATTERN = re.compile(r"['\";\\]|--|\bOR\b|\bAND\b|\bSELECT\b|\bDROP\b", re.IGNORECASE)


def validate_tool_call(name: str, arguments: dict, allowed_tools: set[str] | None = None) -> str | None:
    """
    Returns None if valid, or an error string if invalid.
    allowed_tools defaults to _ALLOWED_TOOLS.
    """
    allowed = allowed_tools or _ALLOWED_TOOLS

    if name not in allowed:
        return f"Unbekanntes Tool '{name}'. Erlaubt: {sorted(allowed)}."

    if name == "get_bank_accounts_by_person_name":
        person_name = arguments.get("person_name")
        if not isinstance(person_name, str):
            return "person_name muss ein String sein."
        person_name = person_name.strip()
        if len(person_name) < _MIN_NAME_LEN:
            return f"person_name zu kurz (min. {_MIN_NAME_LEN} Zeichen)."
        if len(person_name) > _MAX_NAME_LEN:
            return f"person_name zu lang (max. {_MAX_NAME_LEN} Zeichen)."
        # Prompt-injection / SQL-injection check: the value is passed as a
        # parameter, so no real risk, but we flag suspicious patterns as a
        # defence-in-depth measure and return a controlled result instead.
        if _SUSPICIOUS_PATTERN.search(person_name):
            return "person_name enthält unzulässige Zeichen oder Schlüsselwörter."

    return None
