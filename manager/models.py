from dataclasses import dataclass
from typing import Optional


@dataclass
class AppModel:
    id: int
    name: str
    path: str
    entry: str
    host: str
    port: int
    args: Optional[str]
    enabled: bool
