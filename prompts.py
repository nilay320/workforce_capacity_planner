"""
Prompts and context-formatting functions for the Workforce Capacity Planner.

The context formatters transform raw data dicts into clean, readable strings
that the LLM can reason over effectively.
"""

from datetime import date, datetime
from langchain_core.prompts import ChatPromptTemplate

from data import (
    EMPLOYEES,
    PROJECTS,
    get_employee_skills,
    get_employee_allocations,
    get_employee_time_off,
    get_project_requirements,
    get_skill,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an AI Workforce Capacity Planner for an engineering organization.

Your job is to analyze project staffing needs and employee availability, \
then produce specific, data-backed recommendations.

Rules:
- Always use actual names and numbers from the provided data. Never give generic advice.
- For each required skill, explicitly label the situation as one of:
    [TRUE SKILL GAP]    No employee meets the required proficiency level — needs hiring or training.
    [AVAILABILITY GAP]  Qualified employees exist but are fully allocated or on leave — timing issue.
    [COVERAGE RISK]     Only one person qualifies for a critical skill — single point of failure.
    [COVERED]           At least one qualified, available person exists with no concerns.
- When multiple candidates qualify for a skill, rank them by:
    1. Availability — is the person free before the project start date?
    2. Proficiency fit — meets the minimum (not necessarily the highest scorer).
    3. Allocation headroom — lower current allocation is better.
    Explain your ranking explicitly. Do not simply pick the highest proficiency.
- Seniority fit matters: do not assign Staff or Principal engineers to IC-only roles
  when Senior or Mid engineers are qualified and available. Staff engineers are better
  used for oversight, architecture review, or as a last resort.
- "Available from: X" means the employee can begin work on date X. If X is on or
  before the project start date, they are FULLY AVAILABLE for the project.
  Example: project starts 2026-09-01, employee available from 2026-09-01 → available ✅
  Example: project starts 2026-09-01, employee available from 2026-10-01 → NOT available ❌
- Headcount is expressed in FTE (full-time equivalents). 1.0 FTE = one person full-time.
  0.8 FTE = one person at 80% of their time. 1.5 FTE = one full-time + one half-time person.
  When assessing fit, compare the candidate's available allocation % to the FTE needed.
  Example: a requirement of 0.8 FTE needs someone with at least 80% available bandwidth.
- Each person in the RECOMMENDED TEAM must cover exactly one requirement.
  Before finalising, check: does any name appear more than once?
  If yes, find a different qualified person for the extra requirement.
  Only allow a double-assignment if there is literally no other qualified, available
  candidate — and always flag it explicitly as a CRITICAL RISK.
- Use [COVERAGE RISK] when only one employee meets the minimum proficiency for a
  required skill, even if that person is available. [COVERED] requires at least
  two employees who meet the minimum proficiency AND are available by project start.
- Include a RISKS section even when good matches exist.
- Cite your reasoning: reference employee names, allocation end dates, and proficiency scores.
- Proficiency scale: 1=Beginner, 2=Familiar, 3=Proficient, 4=Advanced, 5=Expert.
- Never end with generic conclusions. Every sentence must add specific information.
"""

# ---------------------------------------------------------------------------
# Recommendation prompt template
# ---------------------------------------------------------------------------

RECOMMENDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "PROJECT INFORMATION:\n{project_context}\n\n"
        "EMPLOYEE ROSTER:\n{employee_context}\n\n"
        "Question: {question}"
    )),
])

# ---------------------------------------------------------------------------
# Context formatters
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Gap type label constants — single source of truth used by the system prompt,
# the UI badge colorizer (app.py), and the eval harness (eval/test_cases.py).
# ---------------------------------------------------------------------------

GAP_LABELS: dict[str, str] = {
    "COVERED":          "[COVERED]",
    "AVAILABILITY_GAP": "[AVAILABILITY GAP]",
    "COVERAGE_RISK":    "[COVERAGE RISK]",
    "TRUE_SKILL_GAP":   "[TRUE SKILL GAP]",
}

PROFICIENCY_LABELS = {
    1: "Beginner",
    2: "Familiar",
    3: "Proficient",
    4: "Advanced",
    5: "Expert",
}


def format_project(project_id: str) -> str:
    """Format a single project and its requirements into a readable context block."""
    project = next((p for p in PROJECTS if p["id"] == project_id), None)
    if not project:
        return f"Project {project_id} not found."

    requirements = get_project_requirements(project_id)

    lines = [
        f"Project: {project['name']} ({project['id']})",
        f"Status: {project['status'].title()} | Priority: {project['priority'].title()}",
        f"Timeline: {project['start_date']} → {project['end_date']}",
        f"Description: {project['description']}",
        "",
        "Staffing Requirements:",
    ]
    for req in requirements:
        prof_label = PROFICIENCY_LABELS.get(req["min_proficiency"], str(req["min_proficiency"]))
        fte = req["headcount_needed"]
        fte_str = f"{fte:.1f} FTE" if fte != int(fte) else f"{int(fte)} FTE"
        lines.append(
            f"  - {req['skill_name']}: min proficiency {req['min_proficiency']}/5 ({prof_label}), "
            f"needed: {fte_str}"
        )

    return "\n".join(lines)


def format_all_projects() -> str:
    """Format a summary of all projects (for pipeline-level queries)."""
    sections = []
    for project in PROJECTS:
        lines = [
            f"[{project['id']}] {project['name']}",
            f"  Status: {project['status']} | Priority: {project['priority']}",
            f"  Timeline: {project['start_date']} → {project['end_date']}",
        ]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_employee(employee: dict) -> str:
    """Format a single employee's full profile including skills and current allocation."""
    emp_id = employee["id"]
    skills = get_employee_skills(emp_id)
    allocations = get_employee_allocations(emp_id)
    time_off_entries = get_employee_time_off(emp_id)

    lines = [
        f"{employee['name']} ({emp_id})",
        f"  Role: {employee['role']} | Level: {employee['level'].title()} | "
        f"Type: {employee['employment_type']}",
    ]

    # Skills
    if skills:
        skill_strs = []
        for es in sorted(skills, key=lambda x: x["proficiency"], reverse=True):
            skill = get_skill(es["skill_id"])
            label = PROFICIENCY_LABELS.get(es["proficiency"], str(es["proficiency"]))
            skill_strs.append(
                f"{skill['name']} ({es['proficiency']}/5 — {label}, {es['years_exp']}yr)"
            )
        lines.append(f"  Skills: {' | '.join(skill_strs)}")

    # Current allocations
    if allocations:
        for alloc in allocations:
            project = next((p for p in PROJECTS if p["id"] == alloc["project_id"]), None)
            project_name = project["name"] if project else alloc["project_id"]
            lines.append(
                f"  Allocated: {alloc['allocation_pct']}% on '{project_name}' "
                f"({alloc['start_date']} → {alloc['end_date']})"
            )
        total_pct = sum(a["allocation_pct"] for a in allocations)
        lines.append(f"  Total current allocation: {total_pct}%")
    else:
        lines.append("  Allocation: Currently unallocated (fully available)")

    # Time off
    if time_off_entries:
        for to in time_off_entries:
            lines.append(
                f"  Time off: {to['start_date']} → {to['end_date']} ({to['type']})"
            )

    # Pre-computed availability date — the day after all commitments (allocations + time off) end.
    # This removes date arithmetic from the LLM; compare directly against project start date.
    commitment_end_dates = [
        datetime.strptime(a["end_date"], "%Y-%m-%d").date() for a in allocations
    ] + [
        datetime.strptime(t["end_date"], "%Y-%m-%d").date() for t in time_off_entries
    ]
    if commitment_end_dates:
        latest_end = max(commitment_end_dates)
        from datetime import timedelta
        available_from = latest_end + timedelta(days=1)
        lines.append(f"  *** Available from: {available_from} (compare to project start date) ***")

    # Bio
    lines.append(f"  Bio: {employee['bio']}")

    return "\n".join(lines)


def format_all_employees() -> str:
    """Format the full employee roster for context stuffing."""
    return "\n\n".join(format_employee(emp) for emp in EMPLOYEES)
