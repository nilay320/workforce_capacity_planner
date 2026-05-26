# Workforce Capacity Planner — Todo

Tasks are grouped by iteration. Complete all items in an iteration before starting the next.
Update status inline: `[ ]` pending · `[x]` done · `[-]` in progress · `[~]` deferred

---

## Now — v0 fixes (data model correctness)

- [x] Extract `GAP_LABELS` as constants in `prompts.py`
- [x] Update `app.py` and `eval/test_cases.py` to import `GAP_LABELS`
- [x] Add Arize eval harness (`eval/evaluate.py`, `eval/test_cases.py`)
- [x] Write `SPEC.md`
- [ ] Fix `projects.json`: remove `end_date` from pipeline projects (P003, P004, P006); rename `start_date` → `planned_start_date` for pipeline entries
- [ ] Update `prompts.py::format_project` to render pipeline projects differently (show `planned_start_date`, omit end date, note dates are targets)
- [ ] Update system prompt to treat pipeline `planned_start_date` as an estimate — flag date-based risks rather than hard-blocking candidates
- [ ] Update `.cursor/rules/capstone-data-model.mdc` to reflect the active vs. pipeline date schema split
- [ ] Re-run eval (new dataset `workforce-planner-eval-v2`) after the above changes
- [ ] Commit all of the above

---

## Iteration 2 — Workflow Agent + Retrieval

Goal: Replace context stuffing with targeted retrieval so the system scales beyond a small mock dataset.

### Query classification
- [ ] Add `classify` node to LangGraph that routes to `skill_match`, `staffing_gap`, `capacity_check`, or `headcount_forecast`
- [ ] Add `out_of_scope` handler that gracefully rejects non-workforce questions
- [ ] Add classification evaluator to eval harness

### ChromaDB (semantic search on employee profiles)
- [ ] Set up ChromaDB persistent store in `chroma/`
- [ ] Write `scripts/seed_chroma.py` that embeds employee bios + project descriptions using `text-embedding-3-small`
- [ ] Embed whole documents (not chunked) — include metadata: `type`, `id`, `department`, `level`, `status`
- [ ] Add `retrieve_employees` tool that queries ChromaDB by skill/role keywords
- [ ] Wire tool into `skill_match` routing path

### SQLite (structured queries on allocations/projects)
- [ ] Write `scripts/seed_sqlite.py` that loads all JSON files into SQLite tables matching the spec schema
- [ ] Add `query_allocations` tool using LangChain `create_sql_query_chain`
- [ ] Wire tool into `capacity_check` and `headcount_forecast` routing paths
- [ ] Add hybrid path: ChromaDB candidates → SQL availability filter

### Prompt updates
- [ ] Write per-query-type prompt templates (replacing single `SYSTEM_PROMPT`)
- [ ] Ensure gap label taxonomy is enforced in all templates

### Eval
- [ ] Expand `test_cases.py` with classification test cases
- [ ] Add `query_type_accuracy` evaluator (code-based)
- [ ] Re-run full eval suite on iteration 2; target: all scores ≥ spec floor

---

## Iteration 3 — Autonomous Agent

Goal: Multi-step goal decomposition with tool-calling loop and memory.

- [ ] Design tool registry (skill lookup, availability check, gap analysis, scenario planner)
- [ ] Add `PlannerAgent` node with ReAct loop
- [ ] Add episodic memory (ChromaDB or SQLite) for past staffing decisions
- [ ] Enable multi-hop reasoning ("if we pull David off P005 early, who covers P005?")
- [ ] Add proactive alert capability (over-allocation warnings)
- [ ] Add weekly digest generation
- [ ] Write eval cases for multi-hop reasoning and memory recall

---

## Backlog (no iteration assigned yet)

- [ ] FTE vs. contractor distinction in recommendations (label it explicitly in output)
- [ ] Phase-level project planning (per-phase skill requirements, Gantt-style view)
- [ ] What-if scenario: specific date shift → who becomes available / unavailable
- [ ] Jira / flat-file data ingestion for projects
- [ ] Data write UI (add/edit employees, skills, projects without touching JSON directly)
- [ ] Headcount budget view (total available FTE across org for new work)
