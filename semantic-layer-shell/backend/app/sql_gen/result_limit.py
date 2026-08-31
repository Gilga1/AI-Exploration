from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.config.settings import get_settings


def append_result_limit(sql: str, limit: int | None = None) -> str:
    max_rows = limit if limit is not None else get_settings().max_result_rows
    stripped = sql.rstrip().rstrip(";")
    if re.search(r"\bLIMIT\s+\d+\s*$", stripped, flags=re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {max_rows}"
