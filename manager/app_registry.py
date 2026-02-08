from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from typing import Dict
from manager.app_repository import AppRepository
from manager.models import AppModel



@dataclass(frozen=True)
class AppConfig:
    name: str
    path: str
    entry: str
    default_port: int
    host: str = "127.0.0.1"
    enabled: bool = True


class AppRegistry:
    def __init__(self):
        self.repo = AppRepository()
        self.apps: Dict[str, AppModel] = {}
        self.reload()

    def reload(self):
        apps = self.repo.list()
        self.apps = {a.name: a for a in apps}

    def get_by_id(self, app_id: int) -> AppModel | None:
        return self.repo.get(app_id)
