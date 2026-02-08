Perfect — this is the right moment to **lock the project narrative** so it’s understandable to *you in 6 months* and to *any serious dev* who opens the repo.

Below are **two clean deliverables**:

1. `.gitignore` (tailored to this project, not generic junk)
2. **Detailed README** covering:

   * summary
   * problem
   * solution
   * architecture
   * technical specification
   * functional specification
   * constraints & design decisions

No fluff, no marketing-speak.

---

## 1️⃣ `.gitignore`

```gitignore
# -----------------------------
# Python
# -----------------------------
__pycache__/
*.py[cod]
*.pyo
*.pyd
.env
.venv
venv/
ENV/

# -----------------------------
# FastAPI / Uvicorn
# -----------------------------
*.log
*.pid

# -----------------------------
# OS / Editor
# -----------------------------
.DS_Store
Thumbs.db
.idea/
.vscode/

# -----------------------------
# Node / Frontend tooling (if ever added)
# -----------------------------
node_modules/

# -----------------------------
# Database & Runtime State
# -----------------------------
state/*.db
state/*.db-journal
state/running.json

# -----------------------------
# Build / Cache
# -----------------------------
dist/
build/
.cache/

# -----------------------------
# Secrets (future-proofing)
# -----------------------------
*.key
*.pem
```

📌 **Intentional choices**

* `state/apps.db` ❌ ignored → local registry only
* `running.json` ❌ ignored → ephemeral runtime state
* `apps.yaml` ✅ tracked → import source / documentation

---

## 2️⃣ `README.md` — Detailed, Technical, Honest

```md
# ⚙️ FastAPI App Manager

A **local-first FastAPI process manager** for running, controlling, and monitoring **multiple FastAPI applications** from a single dashboard — without Docker, Kubernetes, or terminal juggling.

This project acts as a **developer-focused supervisor** for FastAPI apps during local development and lightweight staging environments.

---

## 📌 Summary

FastAPI App Manager provides:

- A **SQLite-backed registry** of FastAPI apps
- A **web dashboard** to start, stop, restart, and monitor apps
- Safe **subprocess orchestration** using `uvicorn`
- Clear separation between:
  - *app definition* (persistent)
  - *runtime state* (ephemeral)
- Zero coupling between managed apps

Each managed FastAPI app runs **independently** in its own process and working directory.

---

## ❓ Problem Statement

When working with multiple FastAPI services locally, developers commonly face:

- Multiple terminals running `uvicorn`
- Port collisions
- Forgetting which services are running
- Manual tracking of PIDs
- Editing config files instead of using UI
- Accidental crashes killing everything
- No single source of truth for “what apps exist”

Tools like Docker, PM2, or Supervisor often feel:
- Overkill for local dev
- Non-Python-native
- Opaque or heavyweight

---

## 💡 Solution

This project introduces a **FastAPI-native App Manager** that:

- Treats each FastAPI app as a **managed process**
- Uses **SQLite** as the app registry
- Controls apps using `subprocess + uvicorn`
- Exposes a **clean REST API + HTML UI**
- Never imports or couples managed apps

The manager itself is just **another FastAPI app** — but one that orchestrates others.

---

## 🧠 Core Design Principles

- **No app imports** → no dependency conflicts
- **Explicit ports** → predictable behavior
- **One process per app**
- **Crash isolation** → manager survives child crashes
- **Local-first** → no Docker required
- **Human-readable state**
- **Simple > clever**

---

## 🏗️ Architecture Overview

```

FastAPI App Manager
│
├── SQLite (apps.db)
│   └── App definitions (name, path, entry, port, enabled)
│
├── Process Manager (subprocess)
│   ├── uvicorn app.main:app --port X
│   ├── uvicorn server:app --port Y
│
├── Runtime State (running.json)
│   └── pid, port, timestamps (ephemeral)
│
├── REST API
│   ├── CRUD apps
│   ├── start / stop / restart
│   └── logs
│
└── HTML Dashboard
├── Add / edit apps
├── Start / stop buttons
├── Status indicators
└── Open app links

```

---

## 🧾 Technical Specification

### Backend
- **Language**: Python 3.10+
- **Framework**: FastAPI
- **Server**: Uvicorn
- **Persistence**: SQLite (no ORM)
- **Process control**: `subprocess.Popen`
- **State tracking**:
  - Persistent: SQLite (`apps.db`)
  - Runtime: `running.json` + in-memory tracking

### Frontend
- Plain HTML + CSS + vanilla JS
- No build step
- Auto-refresh polling
- Modal-based CRUD UI

---

## 🗄️ Data Model

### `apps` (SQLite)

| Field | Description |
|-----|------------|
| id | Primary key |
| name | Unique app identifier |
| path | Folder containing the app |
| entry | Uvicorn entry point (`module:app`) |
| host | Bind host (default `127.0.0.1`) |
| port | Assigned port |
| args | Optional uvicorn args |
| enabled | Can app be started |
| created_at | Timestamp |
| updated_at | Timestamp |

---

## 🔌 API Endpoints (Functional Spec)

### App Registry (CRUD)

```

GET    /apps
POST   /apps
PUT    /apps/{id}
DELETE /apps/{id}

```

Rules:
- App names must be unique
- Path must exist and be a directory
- Entry must be `module:app`
- Apps **cannot be edited or deleted while running**

---

### Lifecycle Management

```

POST /apps/{id}/start
POST /apps/{id}/stop
POST /apps/{id}/restart
GET  /apps/{id}/logs

```

Rules:
- Disabled apps cannot be started
- Ports must be free
- Start is idempotent
- Stop cleans runtime state
- Logs are session-scoped (not persisted)

---

### Import Existing Config

```

POST /apps/import-yaml

````

- Imports `config/apps.yaml`
- Upserts apps by name
- Does **not** auto-start apps
- One-time migration helper

---

## 🧪 Runtime Behavior

- Manager checks **actual port availability** to determine running state
- PID existence alone is not trusted
- Manager restart does not reattach to old processes (intentional)
- Runtime state is treated as **best-effort, not authoritative**

---

## 🚫 Non-Goals (By Design)

- No Docker orchestration
- No Kubernetes
- No background job queues
- No distributed deployment
- No auto-scaling
- No auth (local dev tool)

---

## 🧩 Known Limitations

- Browser cannot open native folder picker (security limitation)
- Logs are not persisted across manager restarts
- PID reattachment is intentionally avoided for safety
- Args parsing is simple string split

These are **deliberate tradeoffs**, not oversights.

---

## ▶️ Running the Manager

```bash
pip install -r requirements.txt
uvicorn manager.main:app --reload --port 8000
````

Open:

```
http://127.0.0.1:8000
```

---

## 🔮 Future Enhancements (Optional)

* Auto-assign free ports
* Start/Stop all apps
* Health check endpoints
* Resource usage (CPU/RAM)
* Native wrapper (Tauri / Electron)
* System service (systemd / launchd)

---

## 🏁 Final Notes

This project is intentionally:

* **boring**
* **predictable**
* **transparent**

It exists to remove friction, not introduce abstractions.

If you understand this README, you understand the system.

```

---

If you want next:
- **Architecture diagram (ASCII / SVG)**  
- **API contract doc (OpenAPI-focused)**  
- **“Why not Docker?” rationale doc**  

Say the word.
```

## Run
```bash
pip install -r requirements.txt
uvicorn manager.main:app --reload --port 8000
