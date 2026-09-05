"""
Document Processor
===================
Extracts text from uploaded PDF, DOCX, or TXT files, splits it into
sentences, and filters to those relevant to cybersecurity/data protection
compliance before they are sent for classification.

Filtering matters for two reasons: it keeps inference calls (and therefore
wait time) proportional to the actually-relevant content of a document,
and it avoids flooding the report with irrelevant sentences ("Lunch is at
noon") that would just be noise in the output.
"""

import io
import re

import pdfplumber
from docx import Document as DocxDocument


# ── Cyber-relevant keyword patterns ──────────────────────────
# A sentence is kept for classification if it matches any of these.
# Mirrors the vocabulary used to build the training dataset, so the
# distribution of sentences the model sees at inference time matches
# what it was evaluated on.
CYBER_KEYWORDS = [
    r"\bpasswords?\b", r"\baccess controls?\b",
    r"\buser accounts?\b", r"\baccounts?\b", r"\badmins?\b",
    r"\badministrators?\b",
    r"\bmulti.factor\b", r"\bMFA\b", r"\btwo.factor\b", r"\b2FA\b",
    r"\bprivileged access\b", r"\bshared accounts?\b",
    r"\bantivirus\b", r"\banti.virus\b", r"\bmalware\b",
    r"\bpatch(es|ing)?\b", r"\bsoftware updates?\b",
    r"\bwindows updates?\b", r"\bsecurity updates?\b", r"\bupdates?\b",
    r"\bunsupported\b", r"\bend.of.life\b", r"\boutdated\b",
    r"\bfirewalls?\b", r"\bnetworks?\b", r"\bwifi\b", r"\bwi.fi\b",
    r"\bencrypt(s|ed|ion)?\b", r"\bVPNs?\b",
    r"\bremote access\b", r"\bremote desktops?\b",
    r"\bdata protection\b", r"\bGDPR\b", r"\bconfidential\b",
    r"\bpersonal data\b", r"\bsensitive data\b",
    r"\bdata breach(es)?\b", r"\bICO\b", r"\binformation governance\b",
    r"\bIG\b", r"\bDSPT\b",
    r"\bbackups?\b", r"\bback ?ups?\b", r"\brecovery\b",
    r"\bbusiness continuity\b", r"\bdisaster recovery\b",
    r"\btraining\b", r"\bstaff training\b", r"\bawareness\b",
    r"\bphishing\b", r"\bcyber\w*\b",
    r"\blaptops?\b", r"\bcomputers?\b", r"\bdevices?\b", r"\btablets?\b",
    r"\bUSBs?\b", r"\bremovable media\b",
    r"\bincidents?\b", r"\bbreach(es)?\b", r"\bsecurity incidents?\b",
    r"\bunauthorised access\b", r"\bunauthorized\b",
    r"\bsuppliers?\b", r"\bthird part(y|ies)\b", r"\bcontracts?\b",
    r"\bprocessing agreements?\b", r"\bCyber Essentials\b",
]
CYBER_PATTERN = re.compile("|".join(CYBER_KEYWORDS), re.IGNORECASE)


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Route to the correct extractor based on file extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext in ("docx",):
        return _extract_docx(file_bytes)
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(
            f"Unsupported file type: .{ext}. "
            f"Upload a PDF, Word (.docx), or plain text (.txt) file."
        )


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]

    # Also pull text out of any tables in the document
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)

    return "\n".join(parts)


def split_into_sentences(text: str) -> list[str]:
    """Split raw text into individual sentences."""
    # Normalise whitespace first
    text = re.sub(r"\s+", " ", text).strip()

    # Split on sentence-ending punctuation followed by a space and capital,
    # plus paragraph breaks captured as double newlines before normalisation
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)

    sentences = []
    for s in raw:
        s = s.strip()
        if 15 < len(s) < 400:  # discard fragments and walls of text
            sentences.append(s)

    return sentences


def filter_relevant(sentences: list[str]) -> list[str]:
    """Keep only sentences that touch on cybersecurity/data protection."""
    return [s for s in sentences if CYBER_PATTERN.search(s)]


def process_document(filename: str, file_bytes: bytes) -> dict:
    """
    Full pipeline: extract -> split -> filter.
    Returns counts alongside the filtered sentences so the frontend can
    show "118 of 340 sentences were relevant to compliance" context.
    """
    text = extract_text(filename, file_bytes)
    if not text.strip():
        raise ValueError(
            "No text could be read from this file. "
            "If it's a scanned PDF, it will need to be OCR'd first."
        )

    all_sentences = split_into_sentences(text)
    relevant = filter_relevant(all_sentences)

    return {
        "total_sentences": len(all_sentences),
        "relevant_sentences": relevant,
        "relevant_count": len(relevant),
    }
