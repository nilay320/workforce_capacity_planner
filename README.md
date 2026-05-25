# AI Workforce Capacity Planner

An AI system that helps engineering leaders answer natural language questions about staffing, skill gaps, and resource allocation across their project pipeline.

**Target users:** VP of Engineering, team leads  
**Stack:** LangGraph · LangChain · OpenAI · Streamlit

---

## What it does

Ask questions like:
- *"Who should we assign to the Real-time Analytics Dashboard project?"*
- *"Who is currently over-allocated?"*
- *"Where are our biggest skill gaps for Q4 pipeline projects?"*
- *"Which projects are competing for the same engineers?"*

The system reasons over a mock org dataset — 12 employees, 6 projects, skill inventories, and live allocation data — and returns specific, data-backed recommendations with named candidates, proficiency scores, availability windows, and risk flags.

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/nilay320/workforce_capacity_planner.git
cd workforce_capacity_planner
```

**2. Create and activate a virtual environment**
```bash
uv venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

**3. Install dependencies**
```bash
uv pip install -r requirements.txt
```

**4. Set up your API key**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

---

## Running locally

**Interactive CLI:**
```bash
python main.py
```

**Scoped to a specific project:**
```bash
python main.py --project P004
```

**Single question, non-interactive:**
```bash
python main.py --question "Who should we assign to P004?"
```

**Streamlit UI:**
```bash
python -m streamlit run app.py
# Opens at http://localhost:8501
```

**Live deployment:** [workforce-planner.streamlit.app](https://workforce-planner.streamlit.app)

---

## Project structure

```
├── app.py                  # Streamlit UI
├── planner.py              # LangGraph workflow (load_context → recommend)
├── prompts.py              # System prompt + context formatters
├── data.py                 # JSON loader + lookup helpers
├── main.py                 # CLI entry point
│
├── data/                   # Mock org dataset (edit these to change org data)
│   ├── employees.json
│   ├── skills.json
│   ├── employee_skills.json
│   ├── projects.json
│   ├── project_requirements.json
│   ├── allocations.json
│   └── time_off.json
│
├── .streamlit/
│   └── config.toml         # UI theme (colors, font)
│
├── .cursor/rules/          # Cursor AI rules (always applied in this repo)
├── requirements.txt
└── .env.example
```

---

## Mock data

The `data/` directory contains a fictional mid-size B2B SaaS engineering org:

| Entity | Count |
|---|---|
| Employees | 12 (mix of FTE and contractor) |
| Skills | 20 (technical, domain, leadership) |
| Projects | 6 (3 active, 3 pipeline) |
| Allocations | 11 active assignments |

To modify the org data, edit the JSON files directly — no Python knowledge required.

---

## Three iterations (design progression)

| Iteration | Paradigm | Description |
|---|---|---|
| v0 (current) | Context stuffing | All data loaded into LLM context, single call |
| Iteration 2 | Workflow Agent + Retrieval | ChromaDB (employee profiles) + SQLite (structured data) |
| Iteration 3 | Autonomous Agent | Goal decomposition, tool-calling loop, episodic memory |

---

## Team

Prashant Batra · Andy Ng · Sukhanya Rajan · Javed Jafar · Elaine Park · Nilay Jhaveri · Samrat Chatterjee

*Capstone project — Building Agentic AI Applications with a Problem-First Approach*
