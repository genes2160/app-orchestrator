import json
from pathlib import Path
from typing import Any, Dict

from manager.utils import ensure_dir


class StateStore:
    """
    Persists running state (pid, port, cmd, cwd, timestamps).
    Note: It does NOT guarantee the process is alive; ProcessManager verifies.
    """

    def __init__(self, path: str = "state/running.json"):
        self.path = Path(path)
        ensure_dir(str(self.path.parent))
        if not self.path.exists():
            self.path.write_text(json.dumps({"apps": {}}, indent=2))

    def read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {"apps": {}}

    def write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2))

    def get_app(self, name: str) -> Dict[str, Any] | None:
        data = self.read()
        return data.get("apps", {}).get(name)

    def upsert_app(self, name: str, payload: Dict[str, Any]) -> None:
        data = self.read()
        data.setdefault("apps", {})
        data["apps"][name] = payload
        self.write(data)

    def delete_app(self, name: str) -> None:
        data = self.read()
        apps = data.get("apps", {})
        if name in apps:
            del apps[name]
        data["apps"] = apps
        self.write(data)
