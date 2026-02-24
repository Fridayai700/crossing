"""
crossing.report — generate audit-quality reports from semantic scan results.

Takes JSON output from semantic_scan.py and produces a structured markdown
audit report with executive summary, per-finding analysis, benchmark context,
and methodology notes.

Usage:
    # Pipe from scan
    python3 semantic_scan.py /path/to/project --format json | python3 report.py --name "project"

    # From saved JSON file
    python3 report.py --input scan.json --name "project" --repo "org/project"

    # Scan and report in one step
    python3 report.py --scan /path/to/project --name "project"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone


# Benchmark data from accumulated scans (updated as new projects are scanned)
BENCHMARKS = {
    "flask": {"files": 24, "crossings": 6, "elevated": 2, "density": 0.25},
    "requests": {"files": 18, "crossings": 5, "elevated": 2, "density": 0.28},
    "rich": {"files": 100, "crossings": 5, "elevated": 1, "density": 0.05},
    "celery": {"files": 161, "crossings": 12, "elevated": 3, "density": 0.07},
    "httpx": {"files": 23, "crossings": 3, "elevated": 0, "density": 0.13},
    "fastapi": {"files": 47, "crossings": 0, "elevated": 0, "density": 0.0},
    "hypothesis": {"files": 103, "crossings": 29, "elevated": 7, "density": 0.28},
    "pytest": {"files": 71, "crossings": 9, "elevated": 9, "density": 0.13},
    "click": {"files": 17, "crossings": 11, "elevated": 4, "density": 0.65},
    "tqdm": {"files": 31, "crossings": 7, "elevated": 3, "density": 0.23},
    "uvicorn": {"files": 40, "crossings": 7, "elevated": 3, "density": 0.18},
    "invoke": {"files": 47, "crossings": 12, "elevated": 3, "density": 0.26},
    "scrapy": {"files": 113, "crossings": 23, "elevated": 8, "density": 0.20},
    "colorama": {"files": 7, "crossings": 1, "elevated": 0, "density": 0.14},
}


def _risk_sort_key(crossing: dict) -> int:
    """Sort crossings by risk level (high first)."""
    order = {"high": 0, "elevated": 1, "medium": 2, "low": 3}
    return order.get(crossing.get("risk_level", "low"), 3)


def _classify_overall_risk(crossings: list[dict]) -> str:
    """Determine overall project risk level from crossings."""
    high_count = sum(1 for c in crossings if c["risk_level"] == "high")
    elevated_count = sum(1 for c in crossings if c["risk_level"] == "elevated")
    medium_count = sum(1 for c in crossings if c["risk_level"] == "medium")

    if high_count >= 3:
        return "High"
    elif high_count >= 1 or elevated_count >= 3:
        return "Medium-High"
    elif elevated_count >= 1 or medium_count >= 3:
        return "Medium"
    elif medium_count >= 1:
        return "Low-Medium"
    return "Low"


def _describe_impact(crossing: dict) -> str:
    """Generate a human-readable impact description for a crossing."""
    exc_type = crossing["exception_type"]
    raises = crossing.get("raise_sites", [])
    handlers = crossing.get("handler_sites", [])
    info = crossing.get("information_theory", {})

    raise_count = len(raises)
    handler_count = len(handlers)
    collapse = info.get("collapse_ratio", 0)

    # Group raise sites by function
    functions = set()
    files = set()
    for r in raises:
        functions.add(r.get("function", "unknown"))
        f = r.get("file", "")
        if f:
            files.add(os.path.basename(f))

    # Group handlers by behavior
    reraise_count = sum(1 for h in handlers if h.get("re_raises"))
    return_count = sum(1 for h in handlers if h.get("returns_value"))
    default_count = sum(1 for h in handlers if h.get("assigns_default"))

    parts = []

    # Describe the raise distribution
    if raise_count == 1:
        parts.append(f"Single `{exc_type}` raise site — no semantic ambiguity.")
    elif len(files) > 1:
        parts.append(
            f"`{exc_type}` is raised at {raise_count} sites across "
            f"{len(files)} files ({', '.join(sorted(files))}), "
            f"in {len(functions)} different functions."
        )
    else:
        parts.append(
            f"`{exc_type}` is raised at {raise_count} sites "
            f"in {len(functions)} different functions."
        )

    # Describe handler behavior
    if handler_count == 0:
        parts.append(
            "No local handlers — the exception propagates to the caller with "
            "full semantic information preserved."
        )
    elif handler_count == 1:
        h = handlers[0]
        action = "re-raises" if h.get("re_raises") else (
            "returns a value" if h.get("returns_value") else (
                "assigns a default" if h.get("assigns_default") else "handles"
            )
        )
        parts.append(
            f"A single handler in `{h.get('function', '?')}` "
            f"{action}. With {raise_count} raise sites funneling through "
            f"one handler, semantic disambiguation is impossible."
        )
    else:
        behaviors = []
        if reraise_count:
            behaviors.append(f"{reraise_count} re-raise")
        if return_count:
            behaviors.append(f"{return_count} return")
        if default_count:
            behaviors.append(f"{default_count} assign default")
        parts.append(
            f"{handler_count} handlers ({', '.join(behaviors) if behaviors else 'various behaviors'})."
        )

    # Describe information loss
    if collapse > 0.5:
        bits_lost = info.get("information_loss_bits", 0)
        parts.append(
            f"Information collapse: {collapse:.0%} of semantic information "
            f"is lost ({bits_lost:.1f} bits destroyed)."
        )

    return " ".join(parts)


def _generate_recommendation(crossing: dict) -> str:
    """Generate a recommendation for a crossing."""
    exc_type = crossing["exception_type"]
    raises = crossing.get("raise_sites", [])
    handlers = crossing.get("handler_sites", [])
    risk = crossing.get("risk_level", "low")

    handler_count = len(handlers)
    raise_count = len(raises)

    # Check for implicit raises
    implicit_count = sum(1 for r in raises if r.get("implicit"))
    explicit_count = raise_count - implicit_count

    # Check for single-handler collapse pattern
    if handler_count == 1 and raise_count > 2:
        h = handlers[0]
        if h.get("re_raises"):
            return (
                f"The single handler re-raises, so downstream handlers inherit "
                f"the ambiguity. Consider adding context (e.g., chaining with "
                f"`raise ... from`) or using distinct exception subclasses."
            )
        elif h.get("returns_value") or h.get("assigns_default"):
            return (
                f"Narrow the handler scope: isolate the specific call that "
                f"may raise `{exc_type}` inside the try block, so unrelated "
                f"`{exc_type}` exceptions from other code paths aren't caught."
            )
        else:
            return (
                f"Consider using distinct exception subclasses for the "
                f"{raise_count} different error conditions, or narrow the "
                f"handler to catch only from the expected call site."
            )

    # Mixed explicit + implicit pattern
    if implicit_count > 0 and explicit_count > 0 and handler_count > 0:
        return (
            f"Handlers designed for explicit `{exc_type}` raises also catch "
            f"{implicit_count} implicit source(s) (dict access, type conversions, etc.). "
            f"Consider using `.get()` or EAFP patterns that don't conflate "
            f"the implicit raises with the intentional ones."
        )

    # Standard exception type with many raises
    builtin_types = {
        "ValueError", "TypeError", "KeyError", "AttributeError",
        "RuntimeError", "IndexError", "OSError", "IOError",
    }
    if exc_type in builtin_types and raise_count > 3:
        return (
            f"`{exc_type}` is a broad built-in type carrying "
            f"{raise_count} different meanings here. Consider defining "
            f"project-specific exception subclasses, or narrowing handler "
            f"try-blocks to minimize the catch surface."
        )

    # Multiple handlers — may be adequate
    if handler_count > 1:
        return (
            f"Multiple handlers exist, which may provide adequate "
            f"discrimination. Verify that each handler's try-block scope "
            f"only exposes the expected raise sites."
        )

    if risk == "low":
        return "No action needed."

    return (
        f"Review whether the {handler_count} handler(s) can distinguish "
        f"between the {raise_count} different raise contexts."
    )


def _get_affected_files(crossing: dict, root: str) -> list[str]:
    """Extract unique file paths from a crossing, relative to root."""
    files = set()
    for r in crossing.get("raise_sites", []):
        f = r.get("file", "")
        if f:
            files.add(os.path.relpath(f, root) if root else f)
    for h in crossing.get("handler_sites", []):
        f = h.get("file", "")
        if f:
            files.add(os.path.relpath(f, root) if root else f)
    return sorted(files)


def generate_report(
    scan_data: dict,
    project_name: str,
    repo: str = "",
    version: str = "",
) -> str:
    """Generate a full audit report from scan JSON data."""
    summary = scan_data.get("summary", {})
    crossings = scan_data.get("crossings", [])
    root = scan_data.get("root", "")

    # Sort crossings by risk
    crossings_sorted = sorted(crossings, key=_risk_sort_key)

    # Filter to medium+ for findings section
    significant = [
        c for c in crossings_sorted
        if c.get("risk_level") in ("high", "elevated", "medium")
    ]

    files_scanned = summary.get("files_scanned", 0)
    total_raises = summary.get("total_raises", 0)
    total_handlers = summary.get("total_handlers", 0)
    total_crossings = summary.get("total_crossings", 0)
    risky_crossings = summary.get("risky_crossings", 0)
    mean_collapse = summary.get("mean_collapse_ratio", 0)

    density = total_crossings / files_scanned if files_scanned > 0 else 0
    overall_risk = _classify_overall_risk(crossings)

    # Count by risk level
    high_count = sum(1 for c in crossings if c["risk_level"] == "high")
    elevated_count = sum(1 for c in crossings if c["risk_level"] == "elevated")
    medium_count = sum(1 for c in crossings if c["risk_level"] == "medium")
    low_count = sum(1 for c in crossings if c["risk_level"] == "low")

    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = []

    # Header
    lines.append(f"# Crossing Audit Report: {project_name}")
    lines.append("")
    if repo:
        lines.append(f"**Project:** {project_name} ({repo})")
    else:
        lines.append(f"**Project:** {project_name}")
    if version:
        lines.append(f"**Version:** {version}")
    lines.append(f"**Scanned:** {scan_date}")
    lines.append("**Tool:** Crossing Semantic Scanner v0.9")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    if total_crossings == 0:
        lines.append(
            f"{project_name} has **zero semantic boundary crossings**. "
            f"For a {files_scanned}-file codebase with {total_raises} raise sites "
            f"and {total_handlers} handlers, this is excellent — all exception "
            f"handling is semantically unambiguous."
        )
    else:
        risk_breakdown = []
        if high_count:
            risk_breakdown.append(f"**{high_count} high-risk**")
        if elevated_count:
            risk_breakdown.append(f"**{elevated_count} elevated-risk**")
        if not risk_breakdown and medium_count:
            risk_breakdown.append(f"**{medium_count} medium-risk**")

        crossing_word = "crossing" if total_crossings == 1 else "crossings"

        lines.append(
            f"{project_name} has **{total_crossings} semantic boundary {crossing_word}**, "
            f"including {', '.join(risk_breakdown) if risk_breakdown else 'no significant'} "
            f"findings. For a {files_scanned}-file codebase with {total_raises} raise "
            f"sites and {total_handlers} handlers, this gives a crossing density of "
            f"{density:.2f} per file."
        )

        # Describe concentration
        if significant:
            files_affected = set()
            for c in significant:
                for f in _get_affected_files(c, root):
                    files_affected.add(f)
            if len(files_affected) <= 3:
                lines.append(
                    f"\nThe significant findings are concentrated in "
                    f"{', '.join(f'`{f}`' for f in sorted(files_affected))}."
                )

        lines.append(f"\n**Risk Level:** {overall_risk}.")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Scan Summary Table
    lines.append("## Scan Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Files scanned | {files_scanned} |")
    lines.append(f"| Raise sites | {total_raises} |")
    lines.append(f"| Exception handlers | {total_handlers} |")
    lines.append(f"| Total crossings | {total_crossings} |")
    lines.append(f"| High risk | {high_count} |")
    lines.append(f"| Elevated risk | {elevated_count} |")
    lines.append(f"| Medium risk | {medium_count} |")
    lines.append(f"| Low risk | {low_count} |")
    if mean_collapse > 0:
        lines.append(f"| Mean collapse ratio | {mean_collapse:.0%} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Findings
    if significant:
        lines.append("## Findings")
        lines.append("")

        for crossing in significant:
            risk = crossing["risk_level"].upper()
            exc_type = crossing["exception_type"]
            raises = crossing.get("raise_sites", [])
            handlers = crossing.get("handler_sites", [])
            info = crossing.get("information_theory", {})
            affected_files = _get_affected_files(crossing, root)

            lines.append(
                f"### {risk} RISK: `{exc_type}` — "
                f"{len(raises)} raise site{'s' if len(raises) != 1 else ''}, "
                f"{len(handlers)} handler{'s' if len(handlers) != 1 else ''}"
            )
            lines.append("")

            if affected_files:
                if len(affected_files) == 1:
                    lines.append(f"**File:** `{affected_files[0]}`")
                else:
                    lines.append(f"**Files:** {', '.join(f'`{f}`' for f in affected_files)}")

            # Impact
            lines.append(f"**Impact:** {_describe_impact(crossing)}")
            lines.append("")

            # Raise site details (top 5)
            lines.append("**Raise sites:**")
            for r in raises[:8]:
                func = r.get("function", "?")
                context = r.get("context", "")
                msg = r.get("message")
                implicit = r.get("implicit", False)
                rel_file = os.path.relpath(r.get("file", ""), root) if root else r.get("file", "")
                label = f"`{rel_file}:{r.get('line', '?')}`"
                kind = "implicit" if implicit else "raise"
                detail = f"— {context}" if context else ""
                if msg:
                    detail += f' (`"{msg[:60]}{"..." if len(msg) > 60 else ""}`)'
                lines.append(f"- {label} {kind} `{exc_type}` in `{func}` {detail}")
            if len(raises) > 8:
                lines.append(f"- ... and {len(raises) - 8} more")
            lines.append("")

            # Handler details
            if handlers:
                lines.append("**Handlers:**")
                for h in handlers[:5]:
                    func = h.get("function", "?")
                    action = "re-raises" if h.get("re_raises") else (
                        "returns" if h.get("returns_value") else (
                            "assigns default" if h.get("assigns_default") else "handles"
                        )
                    )
                    rel_file = os.path.relpath(h.get("file", ""), root) if root else h.get("file", "")
                    lines.append(
                        f"- `{rel_file}:{h.get('line', '?')}` — "
                        f"except `{exc_type}` in `{func}` ({action})"
                    )
                if len(handlers) > 5:
                    lines.append(f"- ... and {len(handlers) - 5} more")
                lines.append("")

            # Information theory
            entropy = info.get("semantic_entropy_bits", 0)
            loss = info.get("information_loss_bits", 0)
            collapse = info.get("collapse_ratio", 0)
            if entropy > 0:
                lines.append(
                    f"**Information theory:** {entropy:.1f} bits entropy, "
                    f"{loss:.1f} bits lost, {collapse:.0%} collapse"
                )
                lines.append("")

            # Recommendation
            lines.append(f"**Recommendation:** {_generate_recommendation(crossing)}")
            lines.append("")

    elif total_crossings > 0:
        lines.append("## Findings")
        lines.append("")
        lines.append(
            f"All {total_crossings} crossing{'s are' if total_crossings != 1 else ' is'} low risk. "
            f"No action required."
        )
        lines.append("")

    lines.append("---")
    lines.append("")

    # Benchmark Context
    lines.append("## Benchmark Context")
    lines.append("")
    lines.append("| Project | Files | Crossings | Elevated+ | Density |")
    lines.append("|---------|-------|-----------|-----------|---------|")

    # Add current project first (bold)
    lines.append(
        f"| **{project_name}** | **{files_scanned}** | "
        f"**{total_crossings}** | **{high_count + elevated_count}** | "
        f"**{density:.2f}** |"
    )

    # Add benchmarks, sorted by density descending
    for name, data in sorted(BENCHMARKS.items(), key=lambda x: -x[1]["density"]):
        if name.lower() == project_name.lower():
            continue  # skip if same as current project
        lines.append(
            f"| {name} | {data['files']} | {data['crossings']} | "
            f"{data['elevated']} | {data['density']:.2f} |"
        )

    lines.append("")

    # Density comparison
    densities = [d["density"] for d in BENCHMARKS.values()]
    if densities:
        avg_density = sum(densities) / len(densities)
        if density > avg_density * 1.5:
            lines.append(
                f"{project_name}'s crossing density ({density:.2f}) is "
                f"significantly above the benchmark average ({avg_density:.2f})."
            )
        elif density < avg_density * 0.5:
            lines.append(
                f"{project_name}'s crossing density ({density:.2f}) is "
                f"well below the benchmark average ({avg_density:.2f})."
            )
        else:
            lines.append(
                f"{project_name}'s crossing density ({density:.2f}) is "
                f"in line with the benchmark average ({avg_density:.2f})."
            )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Crossing performs static AST analysis on Python source files. It maps "
        "every `raise` statement to every `except` handler that could catch it, "
        "then identifies **semantic boundary crossings** — places where the same "
        "exception type is raised with different meanings in different contexts. "
        "No code is executed; no network calls are made; no dependencies are required."
    )
    lines.append("")
    lines.append("Risk levels:")
    lines.append("- **Low:** Single raise site or uniform semantics")
    lines.append("- **Medium:** Multiple raise sites in different functions — handler may not distinguish")
    lines.append("- **Elevated:** Many divergent raise sites — high chance of incorrect handling")
    lines.append("- **High:** Handler collapse — many raise sites, very few handlers, ambiguous behavior")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Report generated by [Crossing](https://fridayops.xyz/crossing/) v0.9*  "
    )
    lines.append(f"*Scan performed {scan_date}*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        prog="crossing-report",
        description="Generate audit-quality reports from Crossing semantic scan results.",
    )
    parser.add_argument("--input", "-i", help="JSON file from semantic_scan.py --format json")
    parser.add_argument("--scan", "-s", help="Directory to scan (runs semantic_scan internally)")
    parser.add_argument("--name", "-n", required=True, help="Project name for the report header")
    parser.add_argument("--repo", "-r", default="", help="Repository identifier (e.g., org/project)")
    parser.add_argument("--version", "-v", default="", help="Project version string")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--implicit", action="store_true", help="Include implicit raises in scan")

    args = parser.parse_args()

    if args.scan:
        # Run scan internally
        from semantic_scan import scan_directory
        report = scan_directory(args.scan, detect_implicit=args.implicit)
        scan_data = json.loads(report.to_json())
    elif args.input:
        with open(args.input) as f:
            scan_data = json.load(f)
    else:
        # Read from stdin
        scan_data = json.load(sys.stdin)

    report_md = generate_report(
        scan_data,
        project_name=args.name,
        repo=args.repo,
        version=args.version,
    )

    if args.output:
        with open(args.output, "w") as f:
            f.write(report_md)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report_md)


if __name__ == "__main__":
    main()
