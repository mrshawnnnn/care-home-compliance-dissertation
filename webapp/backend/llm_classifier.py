"""
LLM Classifier
==============
Wraps the locally-hosted Ollama model in the zero-shot compliance
classification prompt. This is the deployed model in the prototype
because zero-shot Mistral was the best-performing condition in the
dissertation's comparative evaluation (macro F1 = 0.926, ahead of the
best supervised classifier at 0.873 and both few-shot conditions).

All inference happens against localhost:11434 — no sentence text is
ever sent to an external API.
"""

import json
import re

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral"

# Identical to the evaluation notebook's SYSTEM_CONTEXT, so the deployed
# model is being asked exactly the question it was benchmarked against.
SYSTEM_CONTEXT = """You are an expert UK care home cybersecurity compliance assessor.

Your task is to classify a statement from a care home document as either COMPLIANT or NON_COMPLIANT based on the following regulatory frameworks:

CYBER ESSENTIALS (5 controls):
- CE1 Firewalls: boundary firewall configured, default passwords changed, inbound blocked by default
- CE2 Secure Configuration: defaults changed, unnecessary software removed, unused accounts disabled
- CE3 Patching: critical updates within 14 days, automatic updates enabled, no unsupported software
- CE4 Access Control: MFA on remote access, least privilege, separate admin accounts, leavers removed
- CE5 Malware Protection: anti-malware active and updated on all devices, email/web filtering

DSPT / NDG STANDARDS (10 standards):
- DSPT1: staff understand data handling responsibilities
- DSPT2: data responsibilities in contracts, breaches acted upon
- DSPT3: annual data security training completed, tested, recorded
- DSPT4: role-based access, access removed when no longer needed
- DSPT5: processes reviewed annually, lessons learned from incidents
- DSPT6: incident response procedure documented, breaches reported to ICO within 72 hours
- DSPT7: business continuity plan, backups taken and tested
- DSPT8: no unsupported systems in use
- DSPT9: data encrypted, cyber strategy based on recognised framework, DSPT submitted
- DSPT10: data processing agreements with all suppliers

RULES:
- A statement is COMPLIANT if it describes a practice that MEETS a control requirement.
- A statement is NON_COMPLIANT if it describes a practice that FAILS to meet a control requirement.
- Focus on what the statement SAYS IS HAPPENING, not what should happen.
- Negation words (no, not, without, never, lack) typically indicate non-compliance.
- Respond with ONLY a JSON object: {"label": "COMPLIANT" or "NON_COMPLIANT", "control": "<control code>", "reason": "<one sentence>"}
- Do NOT add any text before or after the JSON object."""


class OllamaUnavailableError(Exception):
    """Raised when the local Ollama server cannot be reached."""
    pass


def check_ollama_available() -> tuple[bool, str]:
    """Health check — used by the /api/health endpoint."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        if not any(MODEL_NAME in m for m in models):
            return False, (
                f"Ollama is running but '{MODEL_NAME}' is not pulled. "
                f"Run: ollama pull {MODEL_NAME}"
            )
        return True, "ready"
    except requests.exceptions.RequestException:
        return False, (
            "Cannot reach Ollama at localhost:11434. "
            "Start it with: ollama serve"
        )


def build_prompt(sentence: str) -> str:
    return f"""{SYSTEM_CONTEXT}

Statement: "{sentence}"

Classify this statement."""


def _parse_response(raw: str) -> dict:
    """Extract label, control, and reason from the model's JSON output."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            label_str = str(obj.get("label", "")).strip().upper()
            control = str(obj.get("control", "")).strip()
            reason = str(obj.get("reason", "")).strip()

            if "NON" in label_str:
                return {"label": "NON_COMPLIANT", "control": control,
                        "reason": reason, "parse_failed": False}
            elif "COMP" in label_str:
                return {"label": "COMPLIANT", "control": control,
                        "reason": reason, "parse_failed": False}
        except json.JSONDecodeError:
            pass

    # Fallback: keyword search in raw text
    upper = raw.upper()
    if "NON_COMPLIANT" in upper or "NON-COMPLIANT" in upper:
        return {"label": "NON_COMPLIANT", "control": "", "reason": "",
                "parse_failed": False}
    elif "COMPLIANT" in upper:
        return {"label": "COMPLIANT", "control": "", "reason": "",
                "parse_failed": False}

    return {"label": None, "control": "", "reason": raw[:200],
            "parse_failed": True}


def classify_sentence(sentence: str, timeout: int = 60, retries: int = 2) -> dict:
    """
    Classify a single sentence. Returns a dict with label, control,
    reason, and parse_failed. Raises OllamaUnavailableError if the
    server cannot be reached after retries.
    """
    prompt = build_prompt(sentence)
    last_error = None

    for attempt in range(retries + 1):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {"temperature": 0.0, "top_p": 0.1},
                },
                timeout=timeout,
            )
            r.raise_for_status()
            raw = r.json().get("response", "")
            return _parse_response(raw)
        except requests.exceptions.RequestException as e:
            last_error = e

    raise OllamaUnavailableError(
        f"Could not reach the local AI model after {retries + 1} attempts. "
        f"Make sure Ollama is running (`ollama serve`). Detail: {last_error}"
    )
