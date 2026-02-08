import os
import socket
import sys
from typing import Tuple


def is_windows() -> bool:
    return sys.platform.startswith("win")


def port_is_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
