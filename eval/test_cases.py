"""
Eval test cases for the AI Workforce Capacity Planner.

Each test case has:
  question        - the natural language input
  project_id      - optional project scope (mirrors --project flag in CLI)
  expected_labels - gap type labels that must appear in the response
  expected_names  - employee names that must be mentioned
  notes           - why this case tests what it tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prompts import GAP_LABELS  # noqa: E402

L = GAP_LABELS

TEST_CASES = [
    {
        "question": "Who should we assign to the Real-time Analytics Dashboard project (P004)?",
        "project_id": "P004",
        "expected_labels": [L["COVERAGE_RISK"]],
        "expected_names": ["David Park"],
        "notes": (
            "David Park is the only employee meeting min Kafka proficiency of 4. "
            "Alex Rodriguez is on parental leave through August. "
            "Response must flag [COVERAGE RISK] on Kafka."
        ),
    },
    {
        "question": "Who is currently over-allocated?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["Nina Sharma"],
        "notes": (
            "Nina Sharma is at 100% on P002 (Data Platform Migration). "
            "She is the only employee at full allocation in the allocations data."
        ),
    },
    {
        "question": "Who is on leave and when do they return?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["Alex Rodriguez"],
        "notes": (
            "Alex Rodriguez is on parental leave through 2026-08-31, available from 2026-09-01. "
            "This is a factual roster question — the model answers in prose without gap labels. "
            "No expected_labels; validate via name_recall only."
        ),
    },
    {
        "question": "Who is fully unallocated and available for a new project right now?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["Ryan Murphy"],
        "notes": (
            "Ryan Murphy (E012) is the only employee with no active allocations. "
            "Response should name him specifically."
        ),
    },
    {
        "question": "Which projects need Machine Learning expertise at advanced level or above?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": [],
        "notes": (
            "P001 (AI Recommendation Engine) requires Machine Learning at min proficiency 4 (Advanced). "
            "Response should identify P001 and the 2.0 FTE requirement."
        ),
    },
    {
        "question": "What are the skill gaps for the Internal LLM Tooling project (P006)?",
        "project_id": "P006",
        "expected_labels": [L["AVAILABILITY_GAP"]],
        "expected_names": ["Sarah Chen"],
        "notes": (
            "P006 needs LLM/GenAI (min 3) at 1.5 FTE — only Sarah Chen (4) and Tom Wilson (3) qualify. "
            "Python (min 4) has 8 qualified people and should be [COVERED]. "
            "LLM/GenAI has thin bench (2 people for 1.5 FTE) and both may be allocated; "
            "[AVAILABILITY GAP] is the correct label. Sarah Chen is the primary LLM candidate."
        ),
    },
    {
        "question": "Who on the team has healthcare domain knowledge?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["Sarah Chen", "Priya Patel"],
        "notes": (
            "Sarah Chen (S011, proficiency 3) and Priya Patel (S011, proficiency 4) "
            "both have Healthcare Domain skill in employee_skills.json."
        ),
    },
    {
        "question": "Which projects are competing for David Park's time?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["David Park"],
        "notes": (
            "David Park is currently 30% on P005 (Security & Compliance Audit, ends July 2026). "
            "P004 (Real-time Analytics Dashboard) starts Sept 2026 and needs his Kafka expertise. "
            "Response should identify both projects."
        ),
    },
    {
        "question": (
            "What happens to staffing for P004 if the Security & Compliance Audit (P005) "
            "slips by 6 weeks?"
        ),
        "project_id": "P004",
        "expected_labels": [L["AVAILABILITY_GAP"]],
        "expected_names": ["David Park"],
        "notes": (
            "P005 currently ends 2026-07-31. A 6-week slip pushes it to ~2026-09-11. "
            "P004 starts 2026-09-01. David Park would not be free in time, "
            "creating an [AVAILABILITY GAP] on Kafka for P004."
        ),
    },
    {
        "question": "Who are the Kafka candidates on the team and what is their availability?",
        "project_id": None,
        "expected_labels": [],
        "expected_names": ["David Park", "Marcus Johnson"],
        "notes": (
            "David Park has Kafka 5/5, available from 2026-08-01. "
            "Marcus Johnson has Kafka 3/5 — below the typical min of 4 for production systems. "
            "This is a factual roster question — the model answers in prose without gap labels. "
            "Validate via name_recall (both names must appear with proficiency scores)."
        ),
    },
]
