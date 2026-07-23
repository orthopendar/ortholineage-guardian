"""Unified `guardian` command line — a thin façade over the batch scripts (Batch 7).

Each subcommand shells out to the existing `scripts/*.py` / `scripts/*.sh` with the exact
`uv run --with ...` dependency context that script needs, so the scripts remain the single
source of truth and the CLI adds no behaviour of its own. It only unifies the entry points
and prints one line describing each step, so the demo reads as one coherent tool.

    guardian up                     # start DataHub (docker quickstart)
    guardian ingest                 # build + ingest + emit BOTH namespaces
    guardian scan [--namespace]     # run the deterministic policy engine
    guardian artifacts [--namespace]# render PR-ready artifacts into examples/
    guardian writeback [--apply]    # controlled write-back (dry-run unless --apply)
    guardian verify [--expect]      # read the write-back back THROUGH MCP
    guardian reset [--namespace]    # remove everything the guardian wrote
    guardian down [--nuke]          # stop DataHub

The engine decides; the LLM only explains/drafts (schema-validated); write-back is
application code. The CLI never makes a governance decision — it just wires the scripts.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

# Dependency contexts, matched to what each underlying script imports.
_PY = ["uv", "run", "python"]
_PY_MCP = ["uv", "run", "--with", "mcp", "python"]
_PY_WRITE = ["uv", "run", "--with", "mcp", "--with", "acryl-datahub[datahub-rest]", "python"]
_PY_RESET = ["uv", "run", "--with", "acryl-datahub[datahub-rest]", "python"]


def _run(cmd: list[str], doing: str) -> int:
    """Print one line describing the step, then run it from the repo root."""
    print(f"\n\033[1m› guardian: {doing}\033[0m", flush=True)
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


def _script(name: str) -> str:
    return str(SCRIPTS / name)


def _cmd_up(args: argparse.Namespace) -> int:
    return _run(["bash", _script("datahub_up.sh")], "starting DataHub (GMS on :8090)")


def _cmd_ingest(args: argparse.Namespace) -> int:
    return _run(
        ["bash", _script("ingest_all.sh")],
        "building + ingesting + emitting clinical metadata for BOTH namespaces",
    )


def _cmd_scan(args: argparse.Namespace) -> int:
    return _run(
        _PY_MCP + [_script("run_policy_engine.py"), "--namespace", args.namespace],
        f"scanning '{args.namespace}' — deterministic policy engine (metadata only)",
    )


def _cmd_artifacts(args: argparse.Namespace) -> int:
    return _run(
        _PY_MCP + [_script("render_artifacts.py"), "--namespace", args.namespace],
        f"rendering PR-ready artifacts for '{args.namespace}' into examples/",
    )


def _cmd_writeback(args: argparse.Namespace) -> int:
    cmd = _PY_WRITE + [_script("writeback.py"), "--namespace", args.namespace]
    if args.apply:
        cmd.append("--apply")
        doing = f"WRITING findings back to DataHub for '{args.namespace}' (tag + description + incident)"
    else:
        doing = f"write-back DRY-RUN for '{args.namespace}' (nothing written — pass --apply to write)"
    return _run(cmd, doing)


def _cmd_verify(args: argparse.Namespace) -> int:
    return _run(
        _PY_MCP
        + [_script("writeback_verify.py"), "--namespace", args.namespace, "--expect", args.expect],
        f"reading write-back back THROUGH MCP for '{args.namespace}' (expect {args.expect})",
    )


def _cmd_reset(args: argparse.Namespace) -> int:
    return _run(
        _PY_RESET + [_script("writeback_reset.py"), "--namespace", args.namespace],
        f"removing everything the guardian wrote for '{args.namespace}'",
    )


def _cmd_down(args: argparse.Namespace) -> int:
    cmd = ["bash", _script("datahub_down.sh")]
    if args.nuke:
        cmd.append("--nuke")
    return _run(cmd, "stopping DataHub" + (" and wiping volumes" if args.nuke else ""))


def _add_namespace(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--namespace",
        choices=["faulty", "baseline"],
        default="faulty",
        help="which ingested world to act on (default: faulty)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardian",
        description=(
            "OrthoLineage Guardian — a clinically informed, governance-only data-governance "
            "agent. Detect data-contract violations from DataHub metadata, draft remediation, "
            "and write findings back. The engine decides; the LLM only explains/drafts."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    sub.add_parser("up", help="start DataHub (docker quickstart, GMS on :8090)").set_defaults(func=_cmd_up)
    sub.add_parser("ingest", help="build + ingest + emit clinical metadata for both namespaces").set_defaults(func=_cmd_ingest)

    p_scan = sub.add_parser("scan", help="run the deterministic policy engine (metadata only)")
    _add_namespace(p_scan)
    p_scan.set_defaults(func=_cmd_scan)

    p_art = sub.add_parser("artifacts", help="render PR-ready remediation artifacts into examples/")
    _add_namespace(p_art)
    p_art.set_defaults(func=_cmd_artifacts)

    p_wb = sub.add_parser("writeback", help="controlled write-back into DataHub (dry-run unless --apply)")
    _add_namespace(p_wb)
    p_wb.add_argument("--apply", action="store_true", help="actually write (default is dry-run)")
    p_wb.set_defaults(func=_cmd_writeback)

    p_ver = sub.add_parser("verify", help="read the write-back back through MCP")
    _add_namespace(p_ver)
    p_ver.add_argument(
        "--expect", choices=["present", "clean"], default="present",
        help="assert the graph state (present after --apply, clean after reset)",
    )
    p_ver.set_defaults(func=_cmd_verify)

    p_reset = sub.add_parser("reset", help="remove everything the guardian wrote back")
    _add_namespace(p_reset)
    p_reset.set_defaults(func=_cmd_reset)

    p_down = sub.add_parser("down", help="stop DataHub (pass --nuke to wipe volumes)")
    p_down.add_argument("--nuke", action="store_true", help="also delete metadata volumes")
    p_down.set_defaults(func=_cmd_down)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
