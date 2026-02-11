# ⚙️ App Orchestrator

A lightweight, local-first FastAPI application manager that allows you to register, start, stop, restart, and monitor multiple FastAPI applications from a single dashboard — without Docker or Kubernetes.

App Orchestrator is designed for developers who run multiple services locally and want structured process control without heavyweight infrastructure.

---

## 📚 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Manager](#running-the-manager)
- [Using the Dashboard](#using-the-dashboard)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)
- [Limitations](#limitations)
- [Future Improvements](#future-improvements)

---

## 🔍 Overview

App Orchestrator acts as a process supervisor for FastAPI applications.

Instead of manually running:

```
uvicorn app1.main:app --port 8001
uvicorn app2.main:app --port 8002
````

You register the apps once and control them via a UI or API.

It manages:

* App registry (SQLite-backed)
* Subprocess lifecycle (start / stop / restart)
* Port monitoring
* Log streaming
* Runtime state tracking

Each managed app runs as an isolated OS process.

---

## ✨ Features

* ✅ Register multiple FastAPI apps
* ✅ Start / Stop / Restart apps
* ✅ Port conflict detection
* ✅ Real-time log streaming
* ✅ Crash isolation
* ✅ Host + port aware shutdown
* ✅ Cross-platform support (Windows, macOS, Linux)
* ✅ SQLite-based persistent registry
* ✅ No Docker required

---

## 🏗 Architecture

```
App Orchestrator (FastAPI)
│
├── SQLite (state/apps.db)
│   └── Stores app definitions
│
├── Process Manager
│   ├── Uses subprocess.Popen
│   ├── Manages uvicorn processes
│   ├── Tracks PIDs
│   └── Escalates port-based kills if needed
│
├── Runtime State
│   └── state/running.json
│
└── Dashboard (HTML + JS)
```

Each managed app is started via:

```
uvicorn module:app --host <host> --port <port>
```

The manager never imports the app directly.

---

## 🧰 Requirements

* Python 3.10+
* pip
* uvicorn
* FastAPI

---

## 🚀 Installation

Clone the repository:

```
git clone https://github.com/genes2160/app-orchestrator.git
cd app-orchestrator
```

Create virtual environment (recommended):

```
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

Install dependencies:

```
pip install -r requirements.txt
```

---

## ▶️ Running the Manager

Start the orchestrator:

```
uvicorn manager.main:app --reload --port 8000
```

Open in browser:

```
http://127.0.0.1:8000
```

---

## 🖥 Using the Dashboard

1. Add a new app:

   * Name
   * Path to app directory
   * Entry point (e.g. `main:app`)
   * Host
   * Port

2. Click **Start**

3. Monitor logs

4. Stop or Restart as needed

Rules:

* Apps must have unique names
* Ports must not already be in use
* Running apps cannot be edited

---

## 🔌 API Reference

### List Apps

```
GET /apps
```

### Create App

```
POST /apps
```

### Update App

```
PUT /apps/{id}
```

### Delete App

```
DELETE /apps/{id}
```

### Start App

```
POST /apps/{id}/start
```

### Stop App

```
POST /apps/{id}/stop
```

### Restart App

```
POST /apps/{id}/restart
```

### Get Logs

```
GET /apps/{id}/logs
```

---

## 📂 Project Structure

```
app-orchestrator/
│
├── manager/
│   ├── main.py
│   ├── process_manager.py
│   ├── store.py
│   ├── utils.py
│   └── templates/
│
├── state/
│   ├── apps.db
│   └── running.json
│
├── requirements.txt
└── README.md
```

---

## ⚙️ Configuration

App definitions are stored in:

```
state/apps.db
```

Runtime state is stored in:

```
state/running.json
```

You may optionally import apps via YAML if enabled.

---

## 🧠 Design Decisions

* No Docker dependency
* No app imports (process isolation)
* PID-first shutdown
* Port-based escalation kill
* SQLite over ORM for simplicity
* Local-only by design
* No authentication (dev tool)

---

## 🚫 Limitations

* Not intended for production orchestration
* Logs are session-based
* No distributed support
* No container integration
* No authentication layer

This tool is optimized for developer workflows.

---

## 🔮 Future Improvements

* Auto port assignment
* Health check endpoints
* CPU/RAM monitoring
* Start/Stop all apps
* System service integration
* Desktop wrapper (Tauri)

---

## 🏁 Final Notes

App Orchestrator is built to:

* Remove terminal clutter
* Provide deterministic app control
* Keep orchestration simple and transparent

If you run multiple FastAPI services locally, this replaces juggling terminals with structure.

```

