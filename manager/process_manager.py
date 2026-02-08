import os
import signal
import subprocess
import sys
import threading
import select
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
        self._lock = threading.RLock()

    def _tail_init(self, name: str) -> None:
        if name not in self._logs:
            self._logs[name] = deque(maxlen=300)

    def _log(self, name: str, line: str) -> None:
        with self._lock:
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
        startup_timeout: float = 2.0,
    ) -> RunningInfo:
        print(f"\n🧠 [pm.start] called for app='{name}'")

        with self._lock:
            print("🔒 [pm.start] acquired lock")

            if self.is_running(name):
                p = self._procs[name]
                print("⚠️ [pm.start] already running, pid:", p.pid)
                return RunningInfo(
                    name=name,
                    pid=p.pid,
                    port=port,
                    host=host,
                    cwd=cwd,
                    cmd=[],
                    started_at=time.time(),
                )

            print("🔍 [pm.start] checking port:", host, port)
            if port_is_open(host, port):
                print("❌ [pm.start] port already open")
                raise RuntimeError(f"Port {host}:{port} already in use")

            # ----------------------------
            # BUILD COMMAND
            # ----------------------------
            # cmd = ["uvicorn", entry, "--host", host, "--port", str(port)]
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                entry,
                "--host",
                host,
                "--port",
                str(port),
            ]
            if extra_args:
                cmd.extend(extra_args)

            print("🧾 [pm.start] command:", " ".join(cmd))
            print("📂 [pm.start] cwd:", cwd)

            # ----------------------------
            # POPENS KWARGS (THIS WAS MISSING)
            # ----------------------------
            popen_kwargs = dict(
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if is_windows():
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["preexec_fn"] = os.setsid

            # ----------------------------
            # START PROCESS
            # ----------------------------
            self._tail_init(name)
            self._log(name, f"[manager] starting: {' '.join(cmd)}")
            self._log(name, f"[manager] cwd={cwd}")

            try:
                p = subprocess.Popen(cmd, **popen_kwargs)
            except Exception as e:
                print("🔥 [pm.start] Popen failed:", repr(e))
                raise

            print("📌 [pm.start] subprocess started, pid =", p.pid)
            self._procs[name] = p

            # ----------------------------
            # START LOG PUMP THREAD
            # ----------------------------
            print("🧵 [pm.start] starting log pump thread")
            t = threading.Thread(
                target=self._pump_logs,
                args=(name, p),
                daemon=True,
            )
            t.start()

        # ----------------------------
        # WAIT FOR STARTUP / PORT
        # ----------------------------
        print("⏳ [pm.start] entering startup wait loop")

        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            if p.poll() is not None:
                print("💥 [pm.start] process exited early, code:", p.returncode)
                self._log(name, f"[manager] process exited early with code {p.returncode}")
                with self._lock:
                    self._procs.pop(name, None)
                raise RuntimeError("App failed during startup (see logs)")

            if port_is_open(host, port):
                print("✅ [pm.start] port opened successfully")
                self._log(name, "[manager] port opened successfully")
                break

            print("… [pm.start] waiting for port")
            time.sleep(0.1)

        print("🏁 [pm.start] returning RunningInfo")

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
        """
        Cross-platform log pump.
        Safe on Windows.
        Runs in a daemon thread.
        """
        stdout = p.stdout
        if not stdout:
            return

        try:
            for line in iter(stdout.readline, ""):
                if not line:
                    break
                self._log(name, line)
        except Exception as e:
            self._log(name, f"[manager] log pump error: {e}")

    def stop(self, name: str) -> bool:
        with self._lock:
            p = self._procs.get(name)
            if not p or p.poll() is not None:
                return False

            pid = p.pid
            self._log(name, f"[manager] stopping pid={pid}")

            try:
                if is_windows():
                    # Kill process tree on Windows
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception as e:
                self._log(name, f"[manager] stop error: {e}")
                return False

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
