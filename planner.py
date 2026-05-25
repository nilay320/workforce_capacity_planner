"""
LangGraph workflow for the AI Workforce Capacity Planner — Iteration 1.

Graph: START → load_context → recommend → END

State:
  question        Natural language question from the user
  project_id      Which project to focus on (optional; None = org-wide question)
  project_context Formatted project requirements block fed to the LLM
  employee_context Formatted employee roster block fed to the LLM
  recommendation  Final LLM response
"""

import os
from typing import Optional, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END

from prompts import RECOMMENDATION_PROMPT, format_project, format_all_projects, format_all_employees

load_dotenv()


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class PlannerState(TypedDict):
    question: str
    project_id: Optional[str]
    project_context: str
    employee_context: str
    recommendation: str


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def load_context(state: PlannerState) -> dict:
    """Format project and employee data into context strings for the LLM."""
    project_id = state.get("project_id")
    project_context = format_project(project_id) if project_id else format_all_projects()
    employee_context = format_all_employees()
    return {
        "project_context": project_context,
        "employee_context": employee_context,
    }


def recommend(state: PlannerState) -> dict:
    """Call the LLM with full context and return a staffing recommendation."""
    llm = init_chat_model("gpt-4o-mini", model_provider="openai")
    chain = RECOMMENDATION_PROMPT | llm | StrOutputParser()
    response = chain.invoke({
        "project_context": state["project_context"],
        "employee_context": state["employee_context"],
        "question": state["question"],
    })
    return {"recommendation": response}


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(PlannerState)
    graph.add_node("load_context", load_context)
    graph.add_node("recommend", recommend)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "recommend")
    graph.add_edge("recommend", END)
    return graph.compile()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def ask(question: str, project_id: Optional[str] = None) -> str:
    """Run the planner graph and return the recommendation string."""
    result = get_graph().invoke({
        "question": question,
        "project_id": project_id,
        "project_context": "",
        "employee_context": "",
        "recommendation": "",
    })
    return result["recommendation"]
