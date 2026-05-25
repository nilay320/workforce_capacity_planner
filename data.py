"""
Data loader for the AI Workforce Capacity Planner.

Loads all mock org data from JSON files in the data/ directory.
This module is the single import point for all other modules — never
import from data/*.json directly.

JSON files are the source of truth and can be edited by non-engineers.
This module provides typed access and lookup helpers on top of them.
"""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


def _load(filename: str) -> list[dict]:
    with open(_DATA_DIR / filename) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Raw collections (loaded once at import time)
# ---------------------------------------------------------------------------

SKILLS:               list[dict] = _load("skills.json")
EMPLOYEES:            list[dict] = _load("employees.json")
EMPLOYEE_SKILLS:      list[dict] = _load("employee_skills.json")
PROJECTS:             list[dict] = _load("projects.json")
PROJECT_REQUIREMENTS: list[dict] = _load("project_requirements.json")
ALLOCATIONS:          list[dict] = _load("allocations.json")
TIME_OFF:             list[dict] = _load("time_off.json")


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_employee(employee_id: str) -> dict | None:
    return next((e for e in EMPLOYEES if e["id"] == employee_id), None)

def get_project(project_id: str) -> dict | None:
    return next((p for p in PROJECTS if p["id"] == project_id), None)

def get_skill(skill_id: str) -> dict | None:
    return next((s for s in SKILLS if s["id"] == skill_id), None)

def get_employee_skills(employee_id: str) -> list[dict]:
    return [es for es in EMPLOYEE_SKILLS if es["employee_id"] == employee_id]

def get_employee_allocations(employee_id: str) -> list[dict]:
    return [a for a in ALLOCATIONS if a["employee_id"] == employee_id]

def get_employee_time_off(employee_id: str) -> list[dict]:
    return [t for t in TIME_OFF if t["employee_id"] == employee_id]

def get_project_requirements(project_id: str) -> list[dict]:
    return [r for r in PROJECT_REQUIREMENTS if r["project_id"] == project_id]

def get_project_allocations(project_id: str) -> list[dict]:
    return [a for a in ALLOCATIONS if a["project_id"] == project_id]
