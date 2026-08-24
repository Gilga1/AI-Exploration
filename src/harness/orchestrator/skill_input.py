from __future__ import annotations

import re
from typing import Any


def infer_skill_input(skill_name: str, message: str) -> dict[str, Any]:
    if skill_name == "markdown_to_pdf":
        title_match = re.search(r"title[:\s]+(.+)", message, flags=re.IGNORECASE)
        markdown = message
        if "into a pdf" in message.lower():
            markdown = re.sub(r"(?i).*?(notes|markdown)[:\s]*", "", message, count=1)
            markdown = re.sub(r"(?i)\s*into a pdf.*", "", markdown).strip()
        payload: dict[str, Any] = {"markdown": markdown or message}
        if title_match:
            payload["title"] = title_match.group(1).strip()
        return payload
    return {"message": message}
