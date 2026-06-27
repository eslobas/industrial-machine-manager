# 🛠️ Industrial Machine Maintenance Manager

A lightweight **desktop application** to schedule and track preventive maintenance for industrial
machines. Register machines, set the interval until the next service, and get **alerts** when
maintenance is due or overdue. Built in **Python** with a **Tkinter** GUI and a local **SQLite**
database — no server required.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white)
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
gestao_manutencao.py   ─ Tkinter GUI + SQLite data layer (table: manutencao)
alertas_manutencao.py  ─ standalone alert checker (run on login / via Task Scheduler)
manutencao.db          ─ SQLite database (created automatically on first run)
abrir_gestao.bat       ─ Windows launcher
```

**Schema** (`manutencao`): `id`, `nome_maquina`, `data_manutencao`, `dias_para_proxima`,
`data_limite`, `concluida`, `data_conclusao`, `notas`, `pecas_trocadas`.

## 🚀 Getting started

**Prerequisites:** Python 3.8+ (uses only the standard library — `tkinter`, `sqlite3`).

```bash
# Run the app (creates manutencao.db on first launch)
python gestao_manutencao.py

# Check for due/overdue maintenance
python alertas_manutencao.py            # add --pausa to keep the window open
```

On Windows you can double-click `abrir_gestao.bat`. To get daily alerts, schedule
`alertas_manutencao.py` with Windows Task Scheduler at login.

## 🛠️ Tech stack

**Language** · Python 3 · **GUI** · Tkinter · **Storage** · SQLite (file-based) ·
**Platform** · cross-platform core, native notifications on Windows

## 🗺️ Roadmap

- [ ] Export maintenance history to CSV/PDF
- [ ] Cross-platform notifications (plyer)
- [ ] Per-machine history view and filters

---

<sub>Desktop project to practise Python, GUI development and local relational storage with SQLite.</sub>
