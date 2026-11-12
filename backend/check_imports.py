"""Import every backend module once to catch missing packages early.

Run it from a fresh virtual environment after installing requirements.txt.

    python3 check_imports.py
    python3 check_imports.py --allow-missing sentence_transformers

Importing the modules creates the local SQLite file and the static audio
folder, both of which are ignored by git. No network calls are made and no
API key is needed, because llm.py only reads its keys when a request is sent.

The --allow-missing flag lets a run pass when the only problem is a package
you chose not to install, such as sentence_transformers, which pulls in
PyTorch until roadmap item 3 replaces it.
"""

import argparse
import importlib
import os
import sys
import traceback

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Ordered so that shared modules are reported before the ones that use them.
MODULES = [
    "llm",
    "database",
    "agent_engine",
    "document_processor",
    "knowledge_graph",
    "rag_pipeline",
    "study_agent",
    "eval_harness",
    "main",
    "smoke_llm",
]


def check(modules, allow_missing):
    """Return a list of (module, reason, allowed) for every failed import."""
    failures = []
    for name in modules:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            missing = (exc.name or "").split(".")[0]
            failures.append((name, f"missing package {missing}", missing in allow_missing))
        except Exception:  # noqa: BLE001 - report anything that breaks an import
            failures.append((name, traceback.format_exc(limit=3).strip(), False))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--allow-missing",
        action="append",
        default=[],
        metavar="PACKAGE",
        help="top-level package that may be absent without failing the run",
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, BACKEND_DIR)

    failures = check(MODULES, set(args.allow_missing))
    failed = {name for name, _, _ in failures}
    for name in MODULES:
        if name not in failed:
            print(f"ok       {name}")
    for name, reason, allowed in failures:
        label = "skipped" if allowed else "FAILED"
        print(f"{label:8} {name}  ({reason})")

    return 1 if any(not allowed for _, _, allowed in failures) else 0


if __name__ == "__main__":
    sys.exit(main())
