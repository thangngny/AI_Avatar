"""Script service: parse .txt/.docx, count words, estimate speech duration,
and split into renderable segments. Reuses the project's WORDS_PER_SEC
(Vietnamese ~180 wpm, measured in the validated batch).

.docx parsing is dependency-free: a .docx is a zip of XML; we extract
<w:t> text runs from word/document.xml. No python-docx dependency needed.
"""
import os
import re
import zipfile
from typing import Dict, Any, List, Optional
from xml.etree import ElementTree as ET

from . import config

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _extract_docx_text(path: str) -> str:
    """Extract plain text from a .docx without python-docx."""
    parts = []
    with zipfile.ZipFile(path, "r") as z:
        # Main document
        names = z.namelist()
        doc = "word/document.xml"
        if doc not in names:
            # Some docx use a different structure; bail gracefully.
            return ""
        with z.open(doc) as f:
            tree = ET.parse(f)
        root = tree.getroot()
        # Concatenate all <w:t> runs; insert a space at paragraph boundaries
        # (<w:p>). This preserves readability without pulling in formatting.
        for p in root.iter(f"{_W_NS}p"):
            texts = [t.text or "" for t in p.iter(f"{_W_NS}t")]
            para = "".join(texts).strip()
            if para:
                parts.append(para)
        # Footnotes/comments are intentionally ignored (not script content).
    return "\n".join(parts)


def parse_script(file_path: Optional[str] = None,
                 text: Optional[str] = None) -> Dict[str, Any]:
    """Parse a .txt/.docx file or raw text. Returns:
      {ok, text, words, chars, estimated_duration_sec, estimated_duration_str, source}
    """
    if file_path:
        if not os.path.isfile(file_path):
            return {"ok": False, "error": "File not found."}
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = f.read()
            elif ext == ".docx":
                raw = _extract_docx_text(file_path)
                if not raw:
                    return {"ok": False, "error": "Could not read .docx content."}
            else:
                return {"ok": False, "error": f"Unsupported file type: {ext}"}
        except Exception as e:
            return {"ok": False, "error": f"Read error: {e}"}
        source = os.path.basename(file_path)
    elif text is not None:
        raw = text
        source = "Pasted script"
    else:
        return {"ok": False, "error": "No script provided."}

    raw = raw.strip()
    if not raw:
        return {"ok": False, "error": "Script is empty."}

    words = raw.split()
    n_words = len(words)
    dur = n_words / config.WORDS_PER_SEC if config.WORDS_PER_SEC else 0.0
    return {"ok": True, "text": raw, "words": n_words, "chars": len(raw),
            "estimated_duration_sec": round(dur, 1),
            "estimated_duration_str": _fmt_duration(dur),
            "source": source}


def _fmt_duration(sec: float) -> str:
    if sec <= 0:
        return "—"
    m = int(sec) // 60
    s = int(sec) % 60
    if m > 0:
        return f"~{m}m {s}s"
    return f"~{int(sec)}s"


# --------------------------------------------------------------------------- #
# Script splitting                                                            #
# --------------------------------------------------------------------------- #
_SENT_SPLIT = re.compile(r"(?<=[.!?　！？…])\s+")


def _sentences(text: str) -> List[str]:
    parts = _SENT_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_script(text: str, mode: str) -> Dict[str, Any]:
    """Split a script into one or more renderable parts.

    Modes:
      full            -> [entire text]
      30s / 1min / 3min -> first N seconds by words, sentence-boundary aligned
                           (no mid-word / mid-sentence cuts)
      auto            -> sentence-grouped chunks of ~3 min each; final short
                          part rendered as-is (no filler added)

    Returns {ok, mode, parts: [{label, text, words, duration_sec, duration_str}], total}
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Script is empty."}

    if mode == "full":
        return _wrap(mode, [text], ["Full Script"])

    if mode in ("30s", "1min", "3min"):
        sec_map = {"30s": 30.0, "1min": 60.0, "3min": 180.0}
        target_sec = sec_map[mode]
        target_words = max(1, int(target_sec * config.WORDS_PER_SEC))
        sents = _sentences(text)
        # Pack whole sentences up to ~target_words; never cut a sentence.
        buf, n = [], 0
        for s in sents:
            wc = len(s.split())
            if n + wc > target_words and buf:
                break
            buf.append(s)
            n += wc
        part = " ".join(buf) if buf else " ".join(sents[:1])
        return _wrap(mode, [part], [f"First {int(target_sec)}s"])

    if mode == "auto":
        sents = _sentences(text)
        if not sents:
            return _wrap(mode, [text], ["Part 01"])
        target_words = max(20, int(180 * config.WORDS_PER_SEC))  # ~3 min
        parts, labels, buf, n, idx = [], [], [], 0, 1
        for s in sents:
            wc = len(s.split())
            if n + wc > target_words and buf:
                parts.append(" ".join(buf))
                labels.append(f"Part {idx:02d}")
                idx += 1
                buf, n = [s], wc
            else:
                buf.append(s)
                n += wc
        if buf:
            parts.append(" ".join(buf))
            labels.append(f"Part {idx:02d}")
        return _wrap(mode, parts, labels)

    return {"ok": False, "error": f"Unknown split mode: {mode}"}


def _wrap(mode: str, parts: List[str], labels: List[str]) -> Dict[str, Any]:
    out_parts = []
    for label, p in zip(labels, parts):
        wc = len(p.split())
        dur = wc / config.WORDS_PER_SEC if config.WORDS_PER_SEC else 0.0
        out_parts.append({"label": label, "text": p, "words": wc,
                          "duration_sec": round(dur, 1),
                          "duration_str": _fmt_duration(dur)})
    return {"ok": True, "mode": mode, "parts": out_parts,
            "total_parts": len(out_parts)}