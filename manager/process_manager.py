import os
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from manager.utils import is_windows, port_is_open


@dataclass
class RunningInfo:
    name: str
    pid: int
    port: int
    host: str
    cwd: str
    cmd: List[str]
    started_at: float


class ProcessManager:
    """
    In-memory process handle + log tail.
    State persistence is done in StateStore.
    """

    def __init__(self):
        self._procs: Dict[str, subprocess.Popen] = {}
        self._logs: Dict[str, Deque[str]] = {}
        self._lock = threading.Lock()

    def _tail_init(self, name: str) -> None:
        if name not in self._logs:
            self._logs[name] = deque(maxlen=300)

    def _log(self, name: str, line: str) -> None:
        self._tail_init(name)
        self._logs[name].append(line.rstrip("\n"))

    def get_logs(self, name: str) -> list[str]:
        with self._lock:
            self._tail_init(name)
            return list(self._logs[name])

    def is_running(self, name: str) -> bool:
        with self._lock:
            p = self._procs.get(name)
            return bool(p and p.poll() is None)

    def status_from_pid(self, pid: int) -> str:
        if pid <= 0:
            return "stopped"
        try:
            if is_windows():
                # On Windows, kill(0) isn't reliable in the same way; use OpenProcess via psutil (not allowed here).
                # We'll best-effort: if pid exists, it might be alive. The port check below is more meaningful.
                return "unknown"
            os.kill(pid, 0)
            return "running"
        except Exception:
            return "stopped"

    def start(
        self,
        name: str,
        *,
        host: str,
        port: int,
        cwd: str,
        entry: str,
        extra_args: Optional[List[str]] = None,
    ) -> RunningInfo:
        with self._lock:
            if self.is_running(name):
                # already running
                p = self._procs[name]
                return RunningInfo(
                    name=name,
                    pid=p.pid,
                    port=port,
                    host=host,
                    cwd=cwd,
                    cmd=[],
                    started_at=time.time(),
                )

            if port_is_open(host, port):
                raise RuntimeError(f"Port {host}:{port} is already in use")

            cmd = [
                "uvicorn",
                entry,
                "--host",
                host,
                "--port",
                str(port),
            ]

            if extra_args:
                cmd.extend(extra_args)

            # Cross-platform process group handling for clean stop
            popen_kwargs = dict(
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if is_windows():
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                popen_kwargs["stdin"] = subprocess.DEVNULL
            else:
                popen_kwargs["preexec_fn"] = os.setsid  # new process group

            p = subprocess.Popen(cmd, **popen_kwargs)  # type: ignore[arg-type]
            self._procs[name] = p
            self._tail_init(name)
            self._log(name, f"[manager] started pid={p.pid} host={host} port={port} cwd={cwd}")

            t = threading.Thread(target=self._pump_logs, args=(name, p), daemon=True)
            t.start()

            return RunningInfo(
                name=name,
                pid=p.pid,
                port=port,
                host=host,
                cwd=cwd,
                cmd=cmd,
                started_at=time.time(),
            )

    def _pump_logs(self, name: str, p: subprocess.Popen) -> None:
        try:
            if not p.stdout:
                return
            for line in p.stdout:
                self._log(name, line)
        except Exception as e:
            self._log(name, f"[manager] log pump error: {e}")

    def stop(self, name: str) -> bool:
        with self._lock:
            p = self._procs.get(name)
            if not p or p.poll() is not None:
                return False

            pid = p.pid
            try:
                if is_windows():
                    # CTRL_BREAK_EVENT requires a console; best effort: terminate
                    p.terminate()
                else:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)

                self._log(name, f"[manager] stopping pid={pid}")
            except Exception as e:
                self._log(name, f"[manager] stop error: {e}")
                return False

        # wait outside lock
        try:
            p.wait(timeout=6)
        except Exception:
            try:
                with self._lock:
                    if is_windows():
                        p.kill()
                    else:
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    self._log(name, f"[manager] force-killed pid={pid}")
            except Exception:
                pass

        with self._lock:
            self._procs.pop(name, None)

        return True

    def restart(
        self,
        name: str,
        *,
        host: str,
        port: int,
        cwd: str,
        entry: str,
        extra_args: Optional[List[str]] = None,
    ) -> RunningInfo:
        self.stop(name)
        return self.start(
            name,
            host=host,
            port=port,
            cwd=cwd,
            entry=entry,
            extra_args=extra_args,
        )
