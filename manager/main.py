import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from manager.app_registry import AppRegistry
from manager.app_repository import AppRepository
from manager.db import init_db
from manager.process_manager import ProcessManager
from manager.state_store import StateStore
from manager.utils import port_is_open
from manager.validators import validate_app_payload


app = FastAPI(title="FastAPI App Manager", version="0.2.0")

init_db()
repo = AppRepository()
registry = AppRegistry()  # DB-backed
store = StateStore("state/running.json")
pm = ProcessManager()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse("static/index.html")


def _running_entry_for_app_id(app_id: int) -> Optional[Dict[str, Any]]:
    data = store.read()
    for _, meta in (data.get("apps", {}) or {}).items():
        if int(meta.get("app_id", 0) or 0) == int(app_id):
            return meta
    return None


def _is_app_running(app_id: int, host: str, port: int) -> bool:
    meta = _running_entry_for_app_id(app_id)
    # if we have a state entry, verify serving by port (truthy)
    if meta:
        return port_is_open(host, port)
    # If not in state file, still check port
    return port_is_open(host, port)


def _compose_status(app_obj) -> Dict[str, Any]:
    saved = _running_entry_for_app_id(app_obj.id) or {}
    serving = port_is_open(app_obj.host, app_obj.port)
    in_memory_running = pm.is_running(app_obj.name)

    if serving:
        status = "running"
    else:
        status = "starting" if in_memory_running else "stopped"

    return {
        "id": app_obj.id,
        "name": app_obj.name,
        "enabled": app_obj.enabled,
        "path": app_obj.path,
        "entry": app_obj.entry,
        "host": app_obj.host,
        "port": app_obj.port,
        "args": app_obj.args,
        "pid": int(saved.get("pid")) if saved.get("pid") else None,
        "status": status,
        "serving": serving,
        "started_at": saved.get("started_at"),
    }


# -------------------------
# CRUD: Apps
# -------------------------

@app.get("/apps")
def list_apps():
    registry.reload()
    apps = list(registry.apps.values())
    return [ _compose_status(a) for a in apps ]


@app.post("/apps")
def create_app(payload: dict = Body(...)):
    ok, errors = validate_app_payload(payload)
    if not ok:
        raise HTTPException(422, {"errors": errors})

    name = payload["name"].strip()
    if repo.get_by_name(name):
        raise HTTPException(409, "App name already exists")

    created = repo.create(
        name=name,
        path=payload["path"].strip(),
        entry=payload["entry"].strip(),
        port=int(payload["port"]),
        host=(payload.get("host") or "127.0.0.1").strip(),
        args=(payload.get("args") or None),
        enabled=bool(payload.get("enabled", True)),
    )
    registry.reload()
    return _compose_status(created)


@app.put("/apps/{app_id}")
def update_app(app_id: int, payload: dict = Body(...)):
    existing = repo.get(app_id)
    if not existing:
        raise HTTPException(404, "App not found")

    # Prevent edits while running (hard rule)
    if _is_app_running(existing.id, existing.host, existing.port):
        raise HTTPException(400, "Stop app before editing")

    ok, errors = validate_app_payload(payload, is_update=True)
    if not ok:
        raise HTTPException(422, {"errors": errors})

    name = payload["name"].strip()
    if repo.exists_by_name_other_id(name, app_id):
        raise HTTPException(409, "Another app already uses this name")

    updated = repo.update(
        app_id,
        name=name,
        path=payload["path"].strip(),
        entry=payload["entry"].strip(),
        port=int(payload["port"]),
        host=(payload.get("host") or existing.host).strip(),
        args=(payload.get("args") or None),
        enabled=bool(payload.get("enabled", True)),
    )
    registry.reload()
    return _compose_status(updated)


@app.delete("/apps/{app_id}")
def delete_app(app_id: int):
    existing = repo.get(app_id)
    if not existing:
        raise HTTPException(404, "App not found")

    if _is_app_running(existing.id, existing.host, existing.port):
        raise HTTPException(400, "Stop app before deleting")

    deleted = repo.delete(app_id)
    if not deleted:
        raise HTTPException(404, "App not found")

    registry.reload()
    return {"ok": True}


# -------------------------
# Import apps.yaml once → DB
# -------------------------

@app.post("/apps/import-yaml")
def import_apps_yaml(payload: dict = Body(default={})):
    """
    Imports config/apps.yaml into SQLite.
    - Upserts by app name
    - Does NOT start apps
    Optional payload:
      { "path": "config/apps.yaml" }
    """
    config_path = (payload.get("path") or "config/apps.yaml")
    p = Path(config_path)
    if not p.exists():
        raise HTTPException(404, f"YAML not found: {config_path}")

    raw = yaml.safe_load(p.read_text()) or {}
    apps = raw.get("apps", {}) or {}

    imported = []
    for name, cfg in apps.items():
        if not isinstance(cfg, dict):
            continue

        # Allow "enabled" in yaml
        enabled = bool(cfg.get("enabled", True))

        app_obj = repo.upsert_by_name(
            name=str(name),
            path=str(cfg["path"]),
            entry=str(cfg["entry"]),
            port=int(cfg["default_port"]),
            host=str(cfg.get("host", "127.0.0.1")),
            args=str(cfg.get("args")) if cfg.get("args") else None,
            enabled=enabled,
        )
        imported.append(app_obj.name)

    registry.reload()
    return {"ok": True, "imported": imported, "count": len(imported)}


# -------------------------
# Lifecycle: start/stop/restart/logs
# (now uses app_id, not name in URL)
# -------------------------

@app.post("/apps/{app_id}/start")
def start_app(app_id: int):
    print("▶️ start_app called", app_id)

    registry.reload()
    app_obj = repo.get(app_id)
    if not app_obj:
        print("❌ app not found")
        raise HTTPException(404, "App not found")

    print("✅ app loaded:", app_obj.name)

    if not app_obj.enabled:
        print("❌ app disabled")
        raise HTTPException(400, "App is disabled")

    if port_is_open(app_obj.host, app_obj.port):
        print("ℹ️ port already open")
        return {"ok": True, "status": "running", "port": app_obj.port}

    extra_args = ["--reload"]
    if app_obj.args:
        extra_args.extend(app_obj.args.split())

    print("🚀 calling pm.start()")

    try:
        info = pm.start(
            app_obj.name,
            host=app_obj.host,
            port=app_obj.port,
            cwd=app_obj.path,
            entry=app_obj.entry,
            extra_args=extra_args,
        )
    except Exception as e:
        print("🔥 pm.start() raised exception:", repr(e))
        raise

    print("✅ pm.start() returned")
    print("   pid:", info.pid)
    print("   port:", info.port)

    print("💾 writing to state store")
    store.upsert_app(
        app_obj.name,
        {
            "app_id": app_obj.id,
            "pid": info.pid,
            "port": info.port,
            "host": info.host,
            "cwd": info.cwd,
            "cmd": info.cmd,
            "started_at": info.started_at,
        },
    )

    logs = pm.get_logs(app_obj.name)
    print("📜 initial logs count:", len(logs))

    return {
        "ok": True,
        "status": "starting",
        "pid": info.pid,
        "port": info.port,
        "logs": logs[-20:],
    }

@app.post("/apps/{app_id}/stop")
def stop_app(app_id: int):
    registry.reload()
    app_obj = repo.get(app_id)
    if not app_obj:
        raise HTTPException(404, "App not found")

    stopped = pm.stop(app_obj.name)
    store.delete_app(app_obj.name)

    still_serving = port_is_open(app_obj.host, app_obj.port)
    return {"ok": True, "stopped": bool(stopped), "still_serving": still_serving, "port": app_obj.port}


@app.post("/apps/{app_id}/restart")
def restart_app(app_id: int):
    registry.reload()
    app_obj = repo.get(app_id)
    if not app_obj:
        raise HTTPException(404, "App not found")

    if not app_obj.enabled:
        raise HTTPException(400, "App is disabled")

    extra_args = ["--reload"]
    if app_obj.args:
        extra_args.extend(app_obj.args.split())

    try:
        info = pm.restart(
            app_obj.name,
            host=app_obj.host,
            port=app_obj.port,
            cwd=app_obj.path,
            entry=app_obj.entry,
            extra_args=extra_args,
        )
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to restart: {e}")

    store.upsert_app(
        app_obj.name,
        {
            "app_id": app_obj.id,  # ✅ NEW
            "pid": info.pid,
            "port": info.port,
            "host": info.host,
            "cwd": info.cwd,
            "cmd": info.cmd,
            "started_at": time.time(),
        },
    )
    return {"ok": True, "status": "starting", "pid": info.pid, "port": info.port}


@app.get("/apps/{app_id}/logs")
def app_logs(app_id: int):
    registry.reload()
    app_obj = repo.get(app_id)
    if not app_obj:
        raise HTTPException(404, "App not found")
    return {"id": app_obj.id, "name": app_obj.name, "lines": pm.get_logs(app_obj.name)}
