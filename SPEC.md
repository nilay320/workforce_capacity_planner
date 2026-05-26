# AI Workforce Capacity Planner — Specification

> **How to use this document**
> This spec is the authoritative source of truth for the system's behavior and contracts.
> When making changes: update the spec first, then implement. When asking the AI to implement: point to this doc and say "go."
> The Cursor rules in `.cursor/rules/` are the runtime enforcement layer — keep them in sync with this spec.

---

## 1. Problem & Purpose

Engineering leaders (VPs, team leads) at tech companies lack real-time, queryable visibility into workforce capacity. Determining who is available, who has the right skills, and where gaps will emerge across a project pipeline is currently a manual, spreadsheet-driven process.

**The system answers natural language questions about:**
- Who to assign to a project and why
- Where skill or availability gaps exist and what to do about them
- Which engineers are over-allocated or unavailable
- What-if scenarios when project scope or timing changes

**Out of scope:** Hiring decisions, performance management, compensation, org chart changes.

**Output contract:** Every response must use real names and numbers from the data. Generic advice ("find someone with Kafka experience") is a failure mode.

---

## 2. Target Users

| User | Primary need |
|---|---|
| VP of Engineering | Cross-project gap summary; scenario planning before planning meetings |
| Team Lead / Eng Manager | Assignment recommendations; availability checks; early risk flags |
| Project / Program Manager | Resource risk visibility tied to timeline; reforecast inputs |

---

## 3. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Orchestration | LangGraph (`StateGraph` + `TypedDict` state) | Defines the node graph; stateful across nodes |
| LLM | `gpt-4o-mini` (default) | Use `gpt-4o` for complex multi-project synthesis |
| Embeddings | `text-embedding-3-small` | For ChromaDB semantic search (iteration 2+) |
| Vector store | ChromaDB (persistent on disk) | Employee profile + project description retrieval (iteration 2+) |
| Structured data | SQLite via LangChain `create_sql_query_chain` | Allocation and capacity queries (iteration 2+) |
| Frontend | Streamlit | Demo UI; deployed on Streamlit Community Cloud |
| Evaluation | Arize + `arize-phoenix` | LLM-as-judge + code-based evaluators |

---

## 4. Iteration Progression

| Iteration | Paradigm | Key addition | Key limitation |
|---|---|---|---|
| v0 (current) | Context stuffing | All data loaded into LLM context, single call | Doesn't scale beyond small dataset |
| Iteration 2 | Workflow Agent + Retrieval | ChromaDB (profiles) + SQLite (structured data) + query routing | Reactive — one question at a time |
| Iteration 3 | Autonomous Agent | Goal decomposition, tool-calling loop, episodic memory | Higher latency and cost |

### Query classification (iteration 2+)

| Type | Example |
|---|---|
| `staffing_gap` | "Where are we short-staffed for Q4?" |
| `skill_match` | "Who has Kafka experience and is available?" |
| `headcount_forecast` | "How many engineers do we need for a 6-month rebuild?" |
| `capacity_check` | "Is anyone over-allocated right now?" |
| `out_of_scope` | "Can you write a job description?" → graceful rejection |

### Routing logic (iteration 2+)

- `skill_match` and freeform `staffing_gap` → ChromaDB (semantic search on employee profiles)
- `capacity_check` and `headcount_forecast` → SQLite (aggregations on allocations/projects)
- Questions needing both → hybrid (ChromaDB candidates → SQL availability filter)

---

## 5. Data Model Contract

All data lives in `data/*.json`. This section defines the canonical schema and semantics. Code must match this exactly — do not add fields without updating this spec.

### 3.1 employees.json

```
id              string   — e.g. "E001"
name            string
role            string   — job title
department      string
level           enum     — "junior" | "mid" | "senior" | "staff" | "principal"
employment_type enum     — "FTE" | "contractor"
start_date      date     — ISO 8601, employee's hire date
location        string
bio             string   — narrative profile used for semantic search
```

### 3.2 skills.json

```
id              string   — e.g. "S001"
name            string
category        enum     — "technical" | "domain" | "leadership"
```

### 3.3 employee_skills.json

```
employee_id     string   — FK → employees.id
skill_id        string   — FK → skills.id
proficiency     int      — 1–5, see proficiency scale below
years_exp       float    — years of hands-on experience
```

### 3.4 projects.json

Projects have two modes depending on `status`:

**Active projects** (`status: "active"`) — in flight, dates are confirmed facts:
```
id              string
name            string
status          "active"
priority        enum     — "critical" | "high" | "medium" | "low"
start_date      date     — confirmed start, use as fact
end_date        date     — confirmed end, use as fact
description     string
```

**Pipeline projects** (`status: "pipeline"`) — not yet started, dates are targets not facts:
```
id              string
name            string
status          "pipeline"
priority        enum     — "critical" | "high" | "medium" | "low"
planned_start_date  date — target start; treat as estimate, not confirmed
description     string
```

> **Design rationale:** Pipeline projects do not have an `end_date` or `estimated_duration`
> because those are *outputs* of the staffing planning conversation, not inputs.
> The system's job is to reason about who is available when and what that means for
> realistic delivery — pre-populating an end date would answer the question before asking it.
> Do not block engineers from pipeline project assignment based on date overlaps with other
> pipeline projects; treat such overlaps as risks to flag, not hard conflicts.

**Completed projects** (`status: "completed"`):
```
id, name, status: "completed", priority, start_date, end_date, description
```

### 3.5 project_requirements.json

```
project_id      string   — FK → projects.id
skill_id        string   — FK → skills.id
skill_name      string   — denormalized for readability
min_proficiency int      — minimum acceptable proficiency (1–5)
headcount_needed float   — FTE required for this skill on this project
```

### 3.6 allocations.json

```
id              string
employee_id     string   — FK → employees.id
project_id      string   — FK → projects.id
allocation_pct  int      — 0–100, % of employee's time
start_date      date
end_date        date
```

An employee's total allocation across all active rows must not exceed 100%. The system should flag over-allocation, not silently ignore it.

### 3.7 time_off.json

```
employee_id     string   — FK → employees.id
start_date      date
end_date        date
type            string   — e.g. "parental leave", "sabbatical", "PTO"
```

---

## 6. Proficiency Scale

| Level | Label | Meaning |
|---|---|---|
| 1 | Beginner | Tutorial-level; not ready for independent production work |
| 2 | Familiar | Has done real work with it; needs guidance on complex tasks |
| 3 | Proficient | Works independently on standard problems; can own a feature |
| 4 | Advanced | Makes architectural decisions; handles complexity; reviews others |
| 5 | Expert | Go-to person; designs systems; mentors others; spots non-obvious failure modes |

**Setting `min_proficiency` on project requirements:**
- Core skill where wrong decisions sink the project → 4
- Load-bearing but a proficient engineer can handle it → 3
- Supporting role, just can't be starting from zero → 2
- Never use 5 in requirements (no one would qualify)

**FTE semantics:**
`headcount_needed` is fractional full-time equivalents.
- 1.0 = one person full-time
- 0.8 = one person at 80% bandwidth
- 1.5 = one full-time + one half-time person

A candidate with 60% available bandwidth cannot cover a 0.8 FTE requirement.

---

## 7. Gap Type Taxonomy

Every skill requirement in a response must be classified with exactly one label. Labels are defined as constants in `prompts.py` (`GAP_LABELS`) — do not hardcode the strings elsewhere.

| Label | Definition | Recommended action |
|---|---|---|
| `[COVERED]` | ≥2 qualified, available people exist with no concerns | Assign best fit; proceed |
| `[AVAILABILITY GAP]` | Qualified people exist but are fully allocated or on leave before project start | Reschedule, stagger, or wait for commitments to end |
| `[COVERAGE RISK]` | Exactly 1 person meets min proficiency — single point of failure | Document the dependency; add redundancy before go-live |
| `[TRUE SKILL GAP]` | 0 people on the team meet min proficiency | Hire, upskill, or contract |

**Classification rules:**
- `[COVERED]` requires ≥2 people who both meet proficiency AND are available by project start
- `[COVERAGE RISK]` applies even when that 1 person IS available — the risk is the single dependency
- `[AVAILABILITY GAP]` applies when qualified people exist but timing blocks them
- Pipeline project overlaps with other pipeline projects → flag as risk, not hard block

---

## 8. Availability Computation

`available_from` for an employee = the day after the latest end date across all their active allocations and time-off entries.

This computation is done in `prompts.py::format_employee` and surfaced to the LLM as:
```
*** Available from: YYYY-MM-DD (compare to project start date) ***
```

**Date comparison rule:**
- `available_from` ≤ project `start_date` → employee is FULLY AVAILABLE ✅
- `available_from` > project `start_date` → employee is NOT available ❌

The LLM must not perform its own date arithmetic — it reads the pre-computed `available_from` line and compares directly.

---

## 9. LangGraph Workflow Contract (v0)

```
Input:  { question: str, project_id: str | None }
Output: { answer: str }
```

**Nodes:**

`load_context`
- Input: question + optional project_id from state
- Reads all JSON data files via `data.py`
- Formats employee profiles (with pre-computed `available_from`) via `prompts.py::format_all_employees`
- Formats project context via `prompts.py::format_project` (scoped) or `format_all_projects` (all)
- Output: populated `project_context` and `employee_context` strings in state

`recommend`
- Input: project_context + employee_context + question from state
- Calls `gpt-4o-mini` with `SYSTEM_PROMPT` + `RECOMMENDATION_PROMPT`
- Output: `answer` string in state

**Invariants:**
- Every response names actual employees — no anonymous references
- Every skill requirement gets a gap type label
- Every response includes a RISKS section
- No employee appears twice in a recommended team unless explicitly flagged as CRITICAL RISK with justification

---

## 10. System Prompt Contract

The system prompt (`prompts.py::SYSTEM_PROMPT`) enforces:

1. **No generic advice** — every sentence must cite a name, number, or date from the data
2. **Gap labeling** — every required skill is classified with a `GAP_LABELS` label
3. **Candidate ranking** — by availability first, then proficiency fit, then allocation headroom
4. **Seniority fit** — don't assign Staff/Principal to IC-only roles when Senior/Mid are available
5. **FTE matching** — a candidate's available bandwidth must cover the FTE requirement
6. **No double-assignment** — one person covers one requirement; double-assignment requires explicit CRITICAL RISK flag
7. **Date semantics** — read `available_from` directly; do not recompute from raw dates
8. **Pipeline project uncertainty** — treat `planned_start_date` as a target; flag date-based risks as estimates

---

## 11. UI Contract (Streamlit)

**Entry point:** `app.py`, served via `python -m streamlit run app.py`

**Inputs the user controls:**
- Free-text question via `st.chat_input`
- Project scope selector (sidebar) — scopes context to one project or all projects
- Example question buttons (sidebar) — pre-populate the input

**Output rendering:**
- LLM response rendered via `colorize_response()` which replaces `GAP_LABELS` strings with HTML badges
- Badge colors: `[COVERED]` = green, `[COVERAGE RISK]` = yellow, `[TRUE SKILL GAP]` = red, `[AVAILABILITY GAP]` = blue

**State:**
- `st.session_state.messages` — chat history (role + content)
- `st.session_state.pending_question` — bridge between sidebar button clicks and chat input

---

## 12. Eval Contract

Harness: `eval/evaluate.py`. Test cases: `eval/test_cases.py`.

**Evaluators:**

| Name | Type | Pass condition | Score floor |
|---|---|---|---|
| `answer_relevance` | LLM judge (phoenix) | Response addresses the question | ≥ 0.90 |
| `specificity` | LLM judge (phoenix) | Response names real people, not generic advice | ≥ 0.90 |
| `gap_label_recall` | Code-based | Expected gap labels present in response | ≥ 0.80 |
| `name_recall` | Code-based | Expected employee names present in response | ≥ 0.95 |

**Baseline (v1 dataset):** answer_relevance 1.00 · specificity 1.00 · gap_label_recall 0.80 · name_recall 1.00

**Dataset versioning rule:** When `expected_labels` or `expected_names` in `test_cases.py` change, create a new versioned dataset (e.g. `workforce-planner-eval-v2`). `--reuse-dataset` replays the planner against Arize-stored rows — old expectations stay frozen.

---

## 13. What This Spec Does Not Cover

These are intentionally deferred to future iterations:

- Data write operations (adding/editing employees, projects, skills)
- Proactive alerts (over-allocation warnings, weekly digests)
- Jira / external data ingestion
- Semantic search via ChromaDB (iteration 2)
- SQL-based structured queries via SQLite (iteration 2)
- Multi-hop conflict resolution ("if we pull David off P005 early…")
- Historical staffing patterns and memory (iteration 3)
- Phase-level project planning (Gantt view, per-phase skill requirements)
