from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple


def _err(field: str, message: str) -> Dict[str, Any]:
    return {"field": field, "message": message}


def validate_app_payload(payload: Dict[str, Any], *, is_update: bool = False) -> Tuple[bool, list[Dict[str, Any]]]:
    """
    Validates app definition payload (create/update).
    Returns: (ok, errors[])
    """
    errors: list[Dict[str, Any]] = []

    name = (payload.get("name") or "").strip()
    path = (payload.get("path") or "").strip()
    entry = (payload.get("entry") or "").strip()
    host = (payload.get("host") or "127.0.0.1").strip()
    port = payload.get("port")

    if not name:
        errors.append(_err("name", "name is required"))

    if not path:
        errors.append(_err("path", "path is required"))
    else:
        p = Path(path)
        if not p.exists():
            errors.append(_err("path", "path does not exist"))
        elif not p.is_dir():
            errors.append(_err("path", "path must be a folder"))

    if not entry:
        errors.append(_err("entry", "entry is required (example: main:app)"))
    elif ":" not in entry:
        errors.append(_err("entry", "entry must look like 'module:app'"))

    if not host:
        errors.append(_err("host", "host is required"))

    # port
    try:
        port_int = int(port)
        if port_int < 1 or port_int > 65535:
            errors.append(_err("port", "port must be between 1 and 65535"))
    except Exception:
        errors.append(_err("port", "port must be an integer"))

    return (len(errors) == 0, errors)
