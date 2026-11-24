# 🛠️ Industrial Machine Maintenance Manager

Schedule and track preventive maintenance for industrial machines. Register machines, set the
interval until the next service, and get **alerts** when maintenance is due or overdue. Built in
**Python** on a shared **SQLite** data layer, with two front ends: a **FastAPI REST API** and a
**Tkinter** desktop app.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-FFD43B)
![License](https://img.shields.io/badge/license-MIT-blue)

> Interface and code comments are in Portuguese.

---

## ✨ Features

- **Machine registry** — create, search, update and delete maintenance records.
- **Automatic scheduling** — given a service date and an interval (days), the app computes the
  next **due date** (`data_limite`).
- **Status tracking** — mark interventions as completed, with notes and parts replaced.
- **Alerts** — `alertas_manutencao.py` lists machines whose maintenance is due/overdue and shows a
  native Windows notification (falls back to console on other systems); each run is logged.

## 🧱 How it works

```
repositorio.py         ─ data layer: SQLite access, validation, typed errors (no UI code)
api/                   ─ FastAPI REST API, built on repositorio.py
gestao_manutencao.py   ─ Tkinter GUI, built on repositorio.py
alertas_manutencao.py  ─ standalone alert checker (run on login / via Task Scheduler)
tests/                 ─ pytest suite (data layer + API)
manutencao.db          ─ SQLite database (created automatically on first run)
abrir_gestao.bat       ─ Windows launcher
```

The data layer is UI-agnostic: it raises `DadosInvalidos`, `ManutencaoNaoEncontrada` or
`ManutencaoJaConcluida` instead of showing dialogs, so any front end can reuse it. The database
path defaults to `manutencao.db` next to the code and can be overridden with the
`MANUTENCAO_DB` environment variable.

**Schema** (`manutencao`): `id`, `nome_maquina`, `data_manutencao`, `dias_para_proxima`,
`data_limite`, `concluida`, `data_conclusao`, `notas`, `pecas_trocadas`.

## 🚀 Getting started

**Prerequisites:** Python 3.8+ for the desktop app (standard library only — `tkinter`,
`sqlite3`); Python 3.11+ for the REST API.

```bash
# Run the app (creates manutencao.db on first launch)
python gestao_manutencao.py

# Check for due/overdue maintenance
python alertas_manutencao.py            # add --pausa to keep the window open
```

On Windows you can double-click `abrir_gestao.bat`. To get daily alerts, schedule
`alertas_manutencao.py` with Windows Task Scheduler at login.

### REST API

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Interactive docs at <http://localhost:8000/docs>. The API and the desktop app can share the same
`manutencao.db`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/manutencoes` | List all maintenance records (newest first) |
| `POST` | `/manutencoes` | Create a record; `data_limite` is computed → `201` + `Location` |
| `GET` | `/manutencoes/{id}` | Get one record → `404` if missing |
| `POST` | `/manutencoes/{id}/concluir` | Mark as completed (optional body: date, notes, parts) → `409` if already completed |
| `DELETE` | `/manutencoes/{id}` | Delete → `204` / `404` |
| `GET` | `/maquinas/{nome}/historico?ordem=asc\|desc` | Maintenance history of one machine |
| `GET` | `/alertas?data=YYYY-MM-DD` | Pending records due by that date (default today), with `dias_atraso` |

Invalid input returns `422`.

```bash
curl -X POST localhost:8000/manutencoes -H 'content-type: application/json' \
  -d '{"nome_maquina": "Torno CNC 2", "data_manutencao": "2026-11-24", "dias_para_proxima": 90}'
```

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 🛠️ Tech stack

**Language** · Python 3 · **API** · FastAPI + Pydantic · **GUI** · Tkinter ·
**Storage** · SQLite (file-based) · **Tests** · pytest ·
**Platform** · cross-platform core, native notifications on Windows

## 🗺️ Roadmap

- [ ] Export maintenance history to CSV/PDF
- [ ] Cross-platform notifications (plyer)
- [ ] Per-machine history view and filters

---

<sub>Desktop project to practise Python, GUI development and local relational storage with SQLite.</sub>
