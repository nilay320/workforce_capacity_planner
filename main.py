"""
CLI entry point for the AI Workforce Capacity Planner.

Usage:
  python main.py                  # interactive mode
  python main.py --project P004   # scope all questions to a specific project

Examples:
  > Who should we assign to the Real-time Analytics Dashboard project?
  > Who is over-allocated right now?
  > Where are our biggest skill gaps for Q4 pipeline projects?
  > Which projects are competing for the same engineers?
"""

import argparse
import sys

from planner import ask


WELCOME = """
╔══════════════════════════════════════════════════════════╗
║         AI Workforce Capacity Planner                    ║
║         Ask questions about staffing, skills, gaps       ║
║         Type 'quit' or Ctrl-C to exit                    ║
╚══════════════════════════════════════════════════════════╝
"""

EXAMPLE_QUESTIONS = [
    "Who should we assign to the Real-time Analytics Dashboard project (P004)?",
    "Who is currently over-allocated?",
    "Where are our biggest skill gaps for Q4 pipeline projects?",
    "Who has Kafka experience and will be available in September 2026?",
    "Which projects are competing for the same engineers?",
]


def main():
    parser = argparse.ArgumentParser(description="AI Workforce Capacity Planner")
    parser.add_argument(
        "--project", "-p",
        metavar="PROJECT_ID",
        help="Scope questions to a specific project (e.g. P004)",
        default=None,
    )
    parser.add_argument(
        "--question", "-q",
        metavar="QUESTION",
        help="Ask a single question and exit (non-interactive mode)",
        default=None,
    )
    args = parser.parse_args()

    # Non-interactive: single question and exit
    if args.question:
        print(ask(args.question, project_id=args.project))
        return

    # Interactive mode
    print(WELCOME)
    if args.project:
        print(f"  Scoped to project: {args.project}\n")

    print("  Example questions:")
    for q in EXAMPLE_QUESTIONS:
        print(f"    • {q}")
    print()

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        print("\nPlanner: thinking...\n")
        response = ask(question, project_id=args.project)
        print(f"Planner:\n{response}\n")
        print("─" * 60 + "\n")


if __name__ == "__main__":
    main()
