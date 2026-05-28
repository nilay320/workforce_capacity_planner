"""
Streamlit UI for the AI Workforce Capacity Planner.

Run locally:
    python -m streamlit run app.py

Deploy: push to main → Streamlit Cloud auto-deploys.
"""

import streamlit as st
from planner import ask
from data import (
    PROJECTS,
    EMPLOYEES,
    ALLOCATIONS,
    SKILLS,
    EMPLOYEE_SKILLS,
    PROJECT_REQUIREMENTS,
    TIME_OFF,
)
from prompts import GAP_LABELS

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Workforce Capacity Planner",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* App header */
.app-header {
    padding: 1.2rem 0 0.5rem 0;
    border-bottom: 2px solid #2563EB;
    margin-bottom: 1.5rem;
}
.app-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
}
.app-subtitle {
    font-size: 0.9rem;
    color: #64748B;
    margin-top: 0.2rem;
}

/* Sidebar project card */
.project-card {
    background: #DBEAFE;
    border-left: 3px solid #2563EB;
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    margin-top: 0.5rem;
    font-size: 0.82rem;
    color: #1E3A5F;
}

/* Gap type badges in responses */
.badge-covered {
    background: #DCFCE7; color: #166534;
    padding: 1px 7px; border-radius: 10px;
    font-size: 0.78rem; font-weight: 600;
}
.badge-risk {
    background: #FEF9C3; color: #854D0E;
    padding: 1px 7px; border-radius: 10px;
    font-size: 0.78rem; font-weight: 600;
}
.badge-gap {
    background: #FEE2E2; color: #991B1B;
    padding: 1px 7px; border-radius: 10px;
    font-size: 0.78rem; font-weight: 600;
}
.badge-avail {
    background: #E0E7FF; color: #3730A3;
    padding: 1px 7px; border-radius: 10px;
    font-size: 0.78rem; font-weight: 600;
}

/* Example question buttons */
div[data-testid="stButton"] > button {
    text-align: left;
    font-size: 0.8rem;
    padding: 0.4rem 0.7rem;
    border-radius: 6px;
    border: 1px solid #BFDBFE;
    background: white;
    color: #1E40AF;
    width: 100%;
}
div[data-testid="stButton"] > button:hover {
    background: #EFF6FF;
    border-color: #2563EB;
}

/* Chat input area */
div[data-testid="stChatInput"] {
    border-top: 1px solid #E2E8F0;
    padding-top: 0.5rem;
}

/* Metric labels */
div[data-testid="stMetric"] label {
    font-size: 0.75rem !important;
    color: #64748B !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper: colorize gap type labels in LLM response
# ---------------------------------------------------------------------------

def colorize_response(text: str) -> str:
    """Replace gap type labels with colored HTML badges."""
    badge_map = {
        GAP_LABELS["COVERED"]:          '<span class="badge-covered">✅ COVERED</span>',
        GAP_LABELS["COVERAGE_RISK"]:    '<span class="badge-risk">⚠️ COVERAGE RISK</span>',
        GAP_LABELS["TRUE_SKILL_GAP"]:   '<span class="badge-gap">🔴 TRUE SKILL GAP</span>',
        GAP_LABELS["AVAILABILITY_GAP"]: '<span class="badge-avail">🔵 AVAILABILITY GAP</span>',
    }
    for label, badge in badge_map.items():
        text = text.replace(label, badge)
    return text


def project_timeline(project: dict) -> str:
    """Return display-safe timeline text for active and pipeline projects."""
    if project["status"] == "pipeline":
        return f'Target start: {project.get("planned_start_date", "TBD")} (not confirmed)'
    return f'{project["start_date"]} → {project["end_date"]}'


def project_name(project_id: str) -> str:
    project = next((p for p in PROJECTS if p["id"] == project_id), None)
    return project["name"] if project else project_id


def employee_name(employee_id: str) -> str:
    employee = next((e for e in EMPLOYEES if e["id"] == employee_id), None)
    return employee["name"] if employee else employee_id


def skill_name(skill_id: str) -> str:
    skill = next((s for s in SKILLS if s["id"] == skill_id), None)
    return skill["name"] if skill else skill_id


def allocation_summary(employee_id: str) -> int:
    return sum(a["allocation_pct"] for a in ALLOCATIONS if a["employee_id"] == employee_id)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🏗️ Capacity Planner")
    st.caption("AI-powered staffing recommendations for engineering teams.")

    st.divider()

    # Org stats
    active_projects = sum(1 for p in PROJECTS if p["status"] == "active")
    pipeline_projects = sum(1 for p in PROJECTS if p["status"] == "pipeline")
    allocated_employees = len({a["employee_id"] for a in ALLOCATIONS})

    col1, col2 = st.columns(2)
    col1.metric("Employees", len(EMPLOYEES))
    col2.metric("Projects", len(PROJECTS))
    col1.metric("Active", active_projects)
    col2.metric("Pipeline", pipeline_projects)

    st.divider()

    # Project scope selector
    status_icon = {"active": "🟢", "pipeline": "🟡", "completed": "⚪"}
    project_options = {"🌐  All Projects": None} | {
        f"{status_icon.get(p['status'], '⚪')} {p['id']} — {p['name']}": p["id"]
        for p in PROJECTS
    }
    selected_label = st.selectbox(
        "Project scope",
        options=list(project_options.keys()),
        help="Scope your questions to one project, or ask across all.",
    )
    st.caption("🟢 Active · 🟡 Pipeline")
    selected_project_id = project_options[selected_label]

    if selected_project_id:
        project = next(p for p in PROJECTS if p["id"] == selected_project_id)
        priority_color = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            project["priority"], "⚪"
        )
        if project["status"] == "pipeline":
            timeline = f'🎯 {project_timeline(project)}'
        else:
            timeline = f'📅 {project_timeline(project)}'
        st.markdown(
            f'<div class="project-card">'
            f'<strong>{project["name"]}</strong><br>'
            f'Status: <strong>{project["status"].title()}</strong> &nbsp;·&nbsp; '
            f'Priority: {priority_color} {project["priority"].title()}<br>'
            f'{timeline}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Example questions
    st.markdown("**💡 Try asking:**")

    examples = [
        "Who should we assign to the Real-time Analytics Dashboard (P004)?",
        "Who is currently over-allocated?",
        "Where are our biggest skill gaps for Q4 pipeline projects?",
        "Which projects are competing for the same engineers?",
        "Who has Kafka experience and is available in September 2026?",
        "What are the risks if P002 slips by 6 weeks?",
    ]

    for q in examples:
        if st.button(q, use_container_width=True, key=f"btn_{q[:30]}"):
            st.session_state.pending_question = q

    st.divider()

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("pending_question", None)
        st.rerun()

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Main area — header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="app-header">'
    '<p class="app-title">AI Workforce Capacity Planner</p>'
    '<p class="app-subtitle">'
    "Ask natural language questions about staffing, skill gaps, and resource allocation. "
    "Answers are grounded in your org's live employee and project data."
    "</p>"
    "</div>",
    unsafe_allow_html=True,
)

chat_tab, data_tab = st.tabs(["Chat Planner", "Data Explorer"])

with chat_tab:
    # Welcome message when chat is empty
    if not st.session_state.messages:
        st.info(
            "👋 **Get started** — select a project in the sidebar to scope your question, "
            "or ask about the full org. Click an example question or type below.",
            icon=None,
        )

    # ---------------------------------------------------------------------------
    # Chat history
    # ---------------------------------------------------------------------------

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(colorize_response(msg["content"]), unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])

    # ---------------------------------------------------------------------------
    # Input handling
    # ---------------------------------------------------------------------------

    question = None
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")

    typed = st.chat_input("Ask a workforce planning question...")
    if typed:
        question = typed

    # ---------------------------------------------------------------------------
    # Generate response
    # ---------------------------------------------------------------------------

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.messages.append({"role": "user", "content": question})

        with st.chat_message("assistant"):
            with st.spinner("Analyzing org data..."):
                response = ask(question, project_id=selected_project_id)
            st.markdown(colorize_response(response), unsafe_allow_html=True)

        st.session_state.messages.append({"role": "assistant", "content": response})

with data_tab:
    st.markdown("### Data Explorer")
    st.caption(
        "Read-only view of the mock org data used by the planner. "
        "Filters here do not change the underlying JSON files or chat context."
    )

    data_col1, data_col2, data_col3, data_col4 = st.columns(4)
    data_col1.metric("Employees", len(EMPLOYEES))
    data_col2.metric("Skills", len(SKILLS))
    data_col3.metric("Projects", len(PROJECTS))
    data_col4.metric("Allocations", len(ALLOCATIONS))

    st.divider()

    project_statuses = sorted({p["status"] for p in PROJECTS})
    selected_statuses = st.multiselect(
        "Project status",
        options=project_statuses,
        default=project_statuses,
    )
    visible_projects = [p for p in PROJECTS if p["status"] in selected_statuses]
    visible_project_ids = {p["id"] for p in visible_projects}

    project_rows = [
        {
            "ID": p["id"],
            "Name": p["name"],
            "Status": p["status"].title(),
            "Priority": p["priority"].title(),
            "Timeline": project_timeline(p),
        }
        for p in visible_projects
    ]

    st.markdown("#### Projects")
    st.dataframe(project_rows, use_container_width=True, hide_index=True)

    requirement_rows = [
        {
            "Project": project_name(r["project_id"]),
            "Skill": r["skill_name"],
            "Min Proficiency": r["min_proficiency"],
            "FTE Needed": r["headcount_needed"],
        }
        for r in PROJECT_REQUIREMENTS
        if r["project_id"] in visible_project_ids
    ]

    st.markdown("#### Project Requirements")
    st.dataframe(requirement_rows, use_container_width=True, hide_index=True)

    st.divider()

    emp_col1, emp_col2, emp_col3 = st.columns(3)
    levels = sorted({e["level"] for e in EMPLOYEES})
    employment_types = sorted({e["employment_type"] for e in EMPLOYEES})
    skill_options = ["All skills"] + sorted(s["name"] for s in SKILLS)

    selected_levels = emp_col1.multiselect("Employee level", levels, default=levels)
    selected_employment_types = emp_col2.multiselect(
        "Employment type",
        employment_types,
        default=employment_types,
    )
    selected_skill = emp_col3.selectbox("Skill filter", skill_options)

    employee_ids_with_skill = {
        es["employee_id"]
        for es in EMPLOYEE_SKILLS
        if selected_skill == "All skills" or skill_name(es["skill_id"]) == selected_skill
    }

    visible_employees = [
        e for e in EMPLOYEES
        if e["level"] in selected_levels
        and e["employment_type"] in selected_employment_types
        and e["id"] in employee_ids_with_skill
    ]
    visible_employee_ids = {e["id"] for e in visible_employees}

    employee_rows = [
        {
            "ID": e["id"],
            "Name": e["name"],
            "Role": e["role"],
            "Level": e["level"].title(),
            "Employment Type": e["employment_type"],
            "Current Allocation": f'{allocation_summary(e["id"])}%',
            "Location": e["location"],
        }
        for e in visible_employees
    ]

    st.markdown("#### Employees")
    st.dataframe(employee_rows, use_container_width=True, hide_index=True)

    skill_rows = [
        {
            "Employee": employee_name(es["employee_id"]),
            "Skill": skill_name(es["skill_id"]),
            "Proficiency": es["proficiency"],
            "Years Experience": es["years_exp"],
        }
        for es in EMPLOYEE_SKILLS
        if es["employee_id"] in visible_employee_ids
        and (selected_skill == "All skills" or skill_name(es["skill_id"]) == selected_skill)
    ]

    st.markdown("#### Employee Skills")
    st.dataframe(skill_rows, use_container_width=True, hide_index=True)

    st.divider()

    allocation_rows = [
        {
            "Employee": employee_name(a["employee_id"]),
            "Project": project_name(a["project_id"]),
            "Allocation": f'{a["allocation_pct"]}%',
            "Start": a["start_date"],
            "End": a["end_date"],
        }
        for a in ALLOCATIONS
        if a["employee_id"] in visible_employee_ids
    ]

    time_off_rows = [
        {
            "Employee": employee_name(t["employee_id"]),
            "Type": t["type"],
            "Start": t["start_date"],
            "End": t["end_date"],
        }
        for t in TIME_OFF
        if t["employee_id"] in visible_employee_ids
    ]

    alloc_tab, time_off_tab = st.tabs(["Allocations", "Time Off"])
    with alloc_tab:
        st.dataframe(allocation_rows, use_container_width=True, hide_index=True)
    with time_off_tab:
        st.dataframe(time_off_rows, use_container_width=True, hide_index=True)
