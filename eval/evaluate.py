#!/usr/bin/env python3
"""
Arize evaluation runner for the AI Workforce Capacity Planner.

Runs all test cases from test_cases.py through the planner and evaluates:
  1. answer_relevance  — LLM judge (phoenix): does the response address the question?
  2. specificity       — LLM judge (phoenix): does it name actual people, not generic advice?
  3. gap_label_recall  — code-based: correct [COVERAGE RISK] / [AVAILABILITY GAP] etc. present?
  4. name_recall       — code-based: expected employee names mentioned?

Usage:
    # Create a new dataset and run:
    python eval/evaluate.py --dataset-name workforce-planner-eval-v0

    # Re-run against an existing dataset:
    python eval/evaluate.py --dataset-name workforce-planner-eval-v0 --reuse-dataset

Requirements (in requirements.txt):
    arize>=7.0.0
    arize-phoenix>=4.0.0
    OPENAI_API_KEY, ARIZE_API_KEY, ARIZE_SPACE_ID must be set in .env
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Allow running from repo root or eval/ directory
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(str(_REPO_ROOT / ".env"))

from arize import ArizeClient                          # noqa: E402
from arize.experiments import EvaluationResult        # noqa: E402
from phoenix.evals import LLM, create_classifier      # noqa: E402

from planner import ask                               # noqa: E402
from eval.test_cases import TEST_CASES                # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EVAL_MODEL = "gpt-4o-mini"
EXPERIMENT_CONCURRENCY = 1
EXPERIMENT_TIMEOUT_SECONDS = 300
EXPERIMENT_WAIT_MAX_ATTEMPTS = 20
EXPERIMENT_WAIT_SLEEP_SECONDS = 10


# ---------------------------------------------------------------------------
# LLM judge prompts
# ---------------------------------------------------------------------------

ANSWER_RELEVANCE_PROMPT = """
You are comparing a workforce planning question and an AI-generated answer.

[BEGIN DATA]
[Question]: {question}
[Answer]: {actual_output}
[END DATA]

Determine whether the answer is relevant to the question.
Focus on whether the answer addresses the intent and key parts of the question.

Your response must be a single word:
- "relevant" if the answer addresses the question
- "unrelated" if the answer does not address the question
""".strip()


SPECIFICITY_PROMPT = """
You are evaluating whether an AI workforce planning response is specific or generic.

A SPECIFIC response:
- Names actual employees (e.g. "David Park", "Nina Sharma")
- Cites specific data (e.g. proficiency scores, allocation percentages, dates)
- Makes concrete recommendations tied to named individuals

A GENERIC response:
- Gives advice without naming anyone (e.g. "look for engineers with streaming experience")
- Uses placeholder language (e.g. "a qualified candidate", "someone with the right skills")
- Could apply to any org without knowing the actual data

[BEGIN DATA]
[Question]: {question}
[Answer]: {actual_output}
[END DATA]

Your response must be a single word:
- "specific" if the answer names actual people and cites real data
- "generic" if the answer gives advice without grounding it in specific people or data
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _resolve_or_create_dataset(
    client: ArizeClient,
    dataset_name: str,
    space_id: str,
    reuse: bool,
) -> str:
    """Return dataset ID. Creates the dataset if it doesn't exist."""
    page = client.datasets.list(limit=100)
    for dataset in page.datasets:
        if dataset.name == dataset_name:
            if reuse:
                print(f"Reusing existing dataset: {dataset_name} ({dataset.id})")
                return dataset.id
            print(
                f"Dataset '{dataset_name}' already exists. "
                "Use --reuse-dataset to run against it."
            )
            sys.exit(1)

    examples = [
        {
            "question": tc["question"],
            "project_id": tc.get("project_id") or "",
            "expected_labels": ",".join(tc.get("expected_labels", [])),
            "expected_names": ",".join(tc.get("expected_names", [])),
            "notes": tc.get("notes", ""),
        }
        for tc in TEST_CASES
    ]
    dataset = client.datasets.create(
        name=dataset_name,
        space=space_id,
        examples=examples,
    )
    print(f"Created dataset: {dataset_name} ({dataset.id})")
    return dataset.id


def _wait_for_experiment(client: ArizeClient, experiment_id: str) -> None:
    last_error: Exception | None = None
    for _ in range(EXPERIMENT_WAIT_MAX_ATTEMPTS):
        try:
            client.experiments.get(experiment=experiment_id)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(EXPERIMENT_WAIT_SLEEP_SECONDS)
    raise RuntimeError(
        f"Experiment {experiment_id} was not available after waiting."
    ) from last_error


# ---------------------------------------------------------------------------
# Task — single param named `dataset_row` so the SDK passes the row dict directly
# ---------------------------------------------------------------------------

def planner_task(dataset_row: dict[str, Any]) -> dict[str, Any]:
    """Call the planner for one test case and return the output for evaluation."""
    question: str = dataset_row["question"]
    project_id: str | None = dataset_row.get("project_id") or None
    if project_id == "":
        project_id = None

    response = ask(question, project_id=project_id)
    return {
        "question": question,
        "project_id": project_id or "all",
        "actual_output": response,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Arize eval experiment for the Workforce Capacity Planner."
    )
    parser.add_argument("--dataset-name", required=True, help="Arize dataset name.")
    parser.add_argument(
        "--reuse-dataset",
        action="store_true",
        help="Reuse an existing dataset instead of creating a new one.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    required_env = ("OPENAI_API_KEY", "ARIZE_API_KEY", "ARIZE_SPACE_ID")
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    space_id = os.environ["ARIZE_SPACE_ID"]
    arize_client = ArizeClient(api_key=os.environ["ARIZE_API_KEY"])

    dataset_id = _resolve_or_create_dataset(
        arize_client, args.dataset_name, space_id, reuse=args.reuse_dataset
    )
    print(f"Dataset: {args.dataset_name} ({dataset_id})")

    eval_llm = LLM(provider="openai", model=EVAL_MODEL)

    answer_relevance_classifier = create_classifier(
        name="answer_relevance",
        llm=eval_llm,
        prompt_template=ANSWER_RELEVANCE_PROMPT,
        choices={"relevant": 1.0, "unrelated": 0.0},
    )
    specificity_classifier = create_classifier(
        name="specificity",
        llm=eval_llm,
        prompt_template=SPECIFICITY_PROMPT,
        choices={"specific": 1.0, "generic": 0.0},
    )

    # ---------------------------------------------------------------------------
    # Evaluators — positional (dataset_row, output) matching week2 pattern.
    # The SDK wraps these via create_evaluator and calls .evaluate(dataset_row=...,
    # output=...) with keyword args, which binds correctly to positional params.
    # ---------------------------------------------------------------------------

    def answer_relevance_evaluator(
        dataset_row: dict[str, Any], output: dict[str, Any]
    ) -> EvaluationResult:
        score = answer_relevance_classifier.evaluate(
            {
                "question": dataset_row["question"],
                "actual_output": str(output.get("actual_output", "")),
            }
        )[0]
        return EvaluationResult(
            score=float(score.score) if score.score is not None else None,
            label=score.label,
            explanation=score.explanation,
            metadata={"metric": "answer_relevance"},
        )

    def specificity_evaluator(
        dataset_row: dict[str, Any], output: dict[str, Any]
    ) -> EvaluationResult:
        score = specificity_classifier.evaluate(
            {
                "question": dataset_row["question"],
                "actual_output": str(output.get("actual_output", "")),
            }
        )[0]
        return EvaluationResult(
            score=float(score.score) if score.score is not None else None,
            label=score.label,
            explanation=score.explanation,
            metadata={"metric": "specificity"},
        )

    def gap_label_evaluator(
        dataset_row: dict[str, Any], output: dict[str, Any]
    ) -> EvaluationResult:
        """Fraction of expected gap type labels found in the response."""
        expected_raw: str = dataset_row.get("expected_labels", "") or ""
        expected = [lb.strip() for lb in expected_raw.split(",") if lb.strip()]

        if not expected:
            return EvaluationResult(score=1.0, label="pass", explanation="No labels required.")

        response: str = str(output.get("actual_output", ""))
        found = [label for label in expected if label in response]
        score = len(found) / len(expected)
        label = "pass" if score == 1.0 else ("partial" if score > 0 else "fail")
        missing = [lb for lb in expected if lb not in response]
        return EvaluationResult(
            score=score,
            label=label,
            explanation=(
                f"Found {len(found)}/{len(expected)} expected labels. "
                f"Found: {found}. Missing: {missing}"
            ),
            metadata={"metric": "gap_label_recall"},
        )

    def name_recall_evaluator(
        dataset_row: dict[str, Any], output: dict[str, Any]
    ) -> EvaluationResult:
        """Fraction of expected employee names found in the response."""
        expected_raw: str = dataset_row.get("expected_names", "") or ""
        expected = [n.strip() for n in expected_raw.split(",") if n.strip()]

        if not expected:
            return EvaluationResult(score=1.0, label="pass", explanation="No names required.")

        response: str = str(output.get("actual_output", ""))
        found = [name for name in expected if name in response]
        score = len(found) / len(expected)
        label = "pass" if score == 1.0 else ("partial" if score > 0 else "fail")
        missing = [n for n in expected if n not in response]
        return EvaluationResult(
            score=score,
            label=label,
            explanation=(
                f"Found {len(found)}/{len(expected)} expected names. "
                f"Found: {found}. Missing: {missing}"
            ),
            metadata={"metric": "name_recall"},
        )

    experiment_name = f"{args.dataset_name}-{_timestamp()}"
    print(f"Starting experiment: {experiment_name} ({len(TEST_CASES)} test cases)")

    experiment, results_df = arize_client.experiments.run(
        name=experiment_name,
        dataset=dataset_id,
        space=space_id,
        task=planner_task,
        evaluators={
            "answer_relevance": answer_relevance_evaluator,
            "specificity": specificity_evaluator,
            "gap_label_recall": gap_label_evaluator,
            "name_recall": name_recall_evaluator,
        },
        concurrency=EXPERIMENT_CONCURRENCY,
        timeout=EXPERIMENT_TIMEOUT_SECONDS,
        dry_run=False,
    )

    if experiment is None:
        raise RuntimeError("Experiment upload failed: experiment is None.")

    _wait_for_experiment(arize_client, experiment.id)

    print(f"\nExperiment complete.")
    print(f"  Name:   {experiment_name}")
    print(f"  ID:     {experiment.id}")
    print(f"  Rows:   {len(results_df)}")
    print(f"\nView results: https://app.arize.com")

    if not results_df.empty:
        score_cols = [c for c in results_df.columns if c.endswith(".score")]
        if score_cols:
            print("\nMean scores:")
            for col in score_cols:
                mean = results_df[col].mean()
                print(f"  {col.replace('.score', '')}: {mean:.2f}")


if __name__ == "__main__":
    main()
