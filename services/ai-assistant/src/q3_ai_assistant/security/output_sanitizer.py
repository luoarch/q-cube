from __future__ import annotations

import json
import re

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_llm_output(raw_text: str) -> dict | None:
    json_match = _JSON_RE.search(raw_text)
    if not json_match:
        return None

    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    return _deep_strip_html(parsed)


def _deep_strip_html(obj: object) -> object:
    if isinstance(obj, str):
        return _strip_html(obj)
    if isinstance(obj, dict):
        return {k: _deep_strip_html(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_strip_html(item) for item in obj]
    return obj


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)
