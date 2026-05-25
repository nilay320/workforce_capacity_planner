"""
Streamlit UI for the AI Workforce Capacity Planner.

Run locally:
    python -m streamlit run app.py

Deploy: push to main → Streamlit Cloud auto-deploys.
"""

import streamlit as st
from planner import ask
from data import PROJECTS, EMPLOYEES, ALLOCATIONS
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
        st.markdown(
            f'<div class="project-card">'
            f'<strong>{project["name"]}</strong><br>'
            f'Status: <strong>{project["status"].title()}</strong> &nbsp;·&nbsp; '
            f'Priority: {priority_color} {project["priority"].title()}<br>'
            f'📅 {project["start_date"]} → {project["end_date"]}'
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
