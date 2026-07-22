#!/usr/bin/env python3
"""Run a single knowledge-graph Cypher file against Neo4j, feeding it the JSON it expects.

Each data Cypher under ``cypher/`` binds one parameter, ``$docs`` — a list of parsed JSON
documents, one element per source file (see each file's header). This runner maps a Cypher file
to its JSON source folder, loads every JSON there into ``$docs``, splits the Cypher into
statements, and runs each one.

Usage (from the ``kg/`` directory)::

    NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=secret \\
        python load.py --cypher cypher/data_model.cypher

Connection details come from the environment only: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, and the
optional NEO4J_DATABASE. Run one Cypher per invocation; sequence the files yourself. Recommended
order (stubs are ``MERGE``'d, so order matters):

    constraints -> data_model -> behaviour -> service -> flow
    -> interface-sync -> interface-data_access -> component
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Cypher basename -> list of JSON source folders relative to the KG root.
# None  => schema-only, no $docs (constraints.cypher).
# "__COMPONENT__" => the single top-level *--Component--KG.json file.
CYPHER_SOURCES: dict[str, list[str] | None] = {
    "constraints.cypher": None,
    "data_model.cypher": ["data-models"],
    "behaviour.cypher": ["logical-processing-units"],
    "service.cypher": ["services"],
    "flow.cypher": ["flows/compose-engine", "flows/process-manager"],
    "interface-sync.cypher": ["interfaces/sync"],
    "interface-data_access.cypher": ["interfaces/data-access"],
    "component.cypher": ["__COMPONENT__"],
}

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_ROOT = SCRIPT_DIR / "agentic-generator-meta" / "knowledge-graph"


def die(msg: str, code: int = 2) -> None:
    """Print an error to stderr and exit."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def strip_comments(text: str) -> str:
    """Remove ``//`` comments while preserving ``'…'`` strings and ``\\`…\\``` identifiers.

    Cypher uses single quotes for strings (with ``\\`` escapes) and backticks for quoted
    identifiers such as ``x-fbp-params``. A ``//`` inside either is literal text, and so are the
    single ``/`` in ``split(ref, '/')`` and the ``\\n`` in ``'\\n'`` — only ``//`` outside quotes
    starts a comment.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_single = in_back = False
    while i < n:
        c = text[i]
        if in_single:
            out.append(c)
            if c == "\\" and i + 1 < n:  # escape: keep the next char verbatim
                out.append(text[i + 1])
                i += 2
                continue
            if c == "'":
                in_single = False
            i += 1
        elif in_back:
            out.append(c)
            if c == "`":
                in_back = False
            i += 1
        elif c == "'":
            in_single = True
            out.append(c)
            i += 1
        elif c == "`":
            in_back = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":  # skip to end of line
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def split_statements(cypher_text: str) -> list[str]:
    """Split a Cypher file into individual statements on ``;`` after stripping comments."""
    cleaned = strip_comments(cypher_text)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


def collect_docs(json_root: Path, sources: list[str]) -> tuple[list[dict], list[Path]]:
    """Load every JSON file for the mapped source folders into a ``$docs`` list."""
    files: list[Path] = []
    for src in sources:
        if src == "__COMPONENT__":
            files.extend(sorted(json_root.glob("*--Component--KG.json")))
        else:
            folder = json_root / src
            if not folder.is_dir():
                print(f"warning: source folder not found: {folder}", file=sys.stderr)
                continue
            files.extend(sorted(f for f in folder.glob("*.json") if not f.name.startswith("_")))
    docs: list[dict] = []
    for f in files:
        with f.open(encoding="utf-8") as fh:
            docs.append(json.load(fh))
    return docs, files


def run(statements: list[str], docs: list[dict], database: str | None) -> None:
    """Open one session and run each statement with ``$docs`` bound."""
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    for name, val in (("NEO4J_URI", uri), ("NEO4J_USER", user), ("NEO4J_PASSWORD", password)):
        if not val:
            die(f"{name} is not set")

    try:  # imported lazily so --dry-run needs no driver
        from neo4j import GraphDatabase
    except ImportError:
        die("the 'neo4j' driver is not installed. Run: pip install -r requirements.txt")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            for idx, stmt in enumerate(statements, start=1):
                result = session.run(stmt, docs=docs)
                records = list(result)
                # `.keys()` is deliberate: on a neo4j Record `x in record` tests values, not keys.
                totals = [r["total"] for r in records if "total" in r.keys()]  # noqa: SIM118
                suffix = f" -> total={totals[0]}" if totals else ""
                print(f"  [{idx}/{len(statements)}] ok{suffix}")
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one KG Cypher file against Neo4j with its JSON folder as $docs."
    )
    parser.add_argument("--cypher", required=True, help="path to the .cypher file to run")
    parser.add_argument(
        "--json-dir",
        default=str(DEFAULT_JSON_ROOT),
        help=f"KG JSON root (default: {DEFAULT_JSON_ROOT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the resolved source, file count, and statement count without connecting",
    )
    args = parser.parse_args()

    cypher_path = Path(args.cypher)
    if not cypher_path.is_file():
        die(f"cypher file not found: {cypher_path}")

    basename = cypher_path.name
    if basename not in CYPHER_SOURCES:
        known = "\n  ".join(sorted(CYPHER_SOURCES))
        die(f"unknown cypher file '{basename}'. Known files:\n  {known}")

    sources = CYPHER_SOURCES[basename]
    json_root = Path(args.json_dir)
    statements = split_statements(cypher_path.read_text(encoding="utf-8"))

    if sources is None:
        docs, files = [], []
        print(f"{basename}: schema-only (no $docs), {len(statements)} statement(s)")
    else:
        docs, files = collect_docs(json_root, sources)
        print(
            f"{basename}: {len(files)} JSON file(s) from {', '.join(sources)} "
            f"-> $docs, {len(statements)} statement(s)"
        )

    if args.dry_run:
        print("dry-run: not connecting to Neo4j")
        return

    run(statements, docs, os.environ.get("NEO4J_DATABASE"))
    print("done")


if __name__ == "__main__":
    main()
