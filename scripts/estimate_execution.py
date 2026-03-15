#!/usr/bin/env python3
"""Deterministic execution estimator for engineering work items."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from blast_radius import assess_blast_radius
from planning_recommendation import assess_planning_recommendation

POINTS = [1, 2, 3, 5, 8, 13]
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".go", ".h", ".hpp", ".html",
    ".java", ".js", ".json", ".jsx", ".kt", ".kts", ".m", ".md", ".php",
    ".py", ".rb", ".rs", ".scss", ".sh", ".sql", ".swift", ".toml", ".ts",
    ".tsx", ".xml", ".yaml", ".yml", ".zsh",
}
SOURCE_FILENAMES = {
    "Dockerfile", "Makefile", "Brewfile", "Jenkinsfile", "Procfile", "justfile",
}


class EstimationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodebaseMetrics:
    tracked_files: int
    source_files: int
    source_lines: int
    skipped_large_files: int
    skipped_binary_files: int


def run_git(repo_root: Path, args: list[str]) -> str:
    command = ["git", "-C", str(repo_root), *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise EstimationError(
            f"git command failed ({' '.join(command)}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def split_null_terminated(raw: str) -> list[str]:
    return [item for item in raw.split("\0") if item]


def is_source_file(path_str: str) -> bool:
    name = Path(path_str).name
    if name in SOURCE_FILENAMES:
        return True
    return Path(path_str).suffix.lower() in SOURCE_EXTENSIONS


def count_file_lines(path: Path) -> int:
    line_count = 0
    last_chunk_ended_with_newline = True

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            line_count += chunk.count(b"\n")
            last_chunk_ended_with_newline = chunk.endswith(b"\n")

    if path.stat().st_size > 0 and not last_chunk_ended_with_newline:
        line_count += 1

    return line_count


def collect_codebase_metrics(repo_root: Path) -> CodebaseMetrics:
    tracked = split_null_terminated(run_git(repo_root, ["ls-files", "-z"]))
    source_candidates = [path for path in tracked if is_source_file(path)]

    source_lines = 0
    source_files = 0
    skipped_large = 0
    skipped_binary = 0

    for rel_path in source_candidates:
        full_path = repo_root / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue

        try:
            if full_path.stat().st_size > 2 * 1024 * 1024:
                skipped_large += 1
                continue

            with full_path.open("rb") as probe:
                probe_bytes = probe.read(4096)
            if b"\0" in probe_bytes:
                skipped_binary += 1
                continue

            source_lines += count_file_lines(full_path)
            source_files += 1
        except OSError:
            continue

    return CodebaseMetrics(
        tracked_files=len(tracked),
        source_files=source_files,
        source_lines=source_lines,
        skipped_large_files=skipped_large,
        skipped_binary_files=skipped_binary,
    )


def normalize_paths(paths: Iterable[str]) -> list[str]:
    cleaned = sorted({path.strip() for path in paths if path.strip()})
    return cleaned


def top_level_dirs(paths: Iterable[str]) -> list[str]:
    levels = sorted({path.split("/", 1)[0] if "/" in path else "<root>" for path in paths if path})
    return levels


def estimate_lines_for_path(path: str) -> int:
    normalized = path.lower()
    suffix = Path(path).suffix.lower()

    if normalized.startswith("docs/") or suffix in {".md", ".mdx"}:
        return 25
    if suffix in {".yml", ".yaml", ".json", ".toml"}:
        return 35
    if "/test" in normalized or suffix in {".spec.ts", ".test.ts", ".spec.js", ".test.js"}:
        return 60
    if suffix in {".sql"}:
        return 120
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java", ".kt", ".swift"}:
        return 90
    return 70


def collect_diff_change(repo_root: Path, base_ref: str, head_ref: str) -> dict:
    revision = f"{base_ref}...{head_ref}"
    names_raw = run_git(repo_root, ["diff", "--name-only", "--diff-filter=ACDMRTUXB", revision])
    files = normalize_paths(names_raw.splitlines())

    numstat_raw = run_git(repo_root, ["diff", "--numstat", revision])
    added = 0
    deleted = 0
    binaries = 0
    max_file_churn = 0

    for line in numstat_raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s = parts[0], parts[1]

        if add_s == "-" or del_s == "-":
            binaries += 1
            continue

        add_v = int(add_s)
        del_v = int(del_s)
        added += add_v
        deleted += del_v
        max_file_churn = max(max_file_churn, add_v + del_v)

    return {
        "mode": "diff",
        "files": files,
        "files_touched": len(files),
        "lines_added": added,
        "lines_deleted": deleted,
        "lines_changed": added + deleted,
        "binaries_touched": binaries,
        "max_file_churn": max_file_churn,
        "dirs_touched": top_level_dirs(files),
    }


def collect_proposal_change(proposed_file_path: Path, override_lines_changed: int | None) -> dict:
    raw_paths = proposed_file_path.read_text(encoding="utf-8").splitlines()
    files = normalize_paths(raw_paths)

    estimated_per_file = [estimate_lines_for_path(path) for path in files]
    estimated_lines_changed = sum(estimated_per_file)
    if override_lines_changed is not None:
        estimated_lines_changed = override_lines_changed

    lines_added = int(round(estimated_lines_changed * 0.6))
    lines_deleted = estimated_lines_changed - lines_added

    return {
        "mode": "proposal",
        "files": files,
        "files_touched": len(files),
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "lines_changed": estimated_lines_changed,
        "binaries_touched": 0,
        "max_file_churn": max(estimated_per_file) if estimated_per_file else 0,
        "dirs_touched": top_level_dirs(files),
    }


def base_story_points(lines_changed: int) -> int:
    if lines_changed <= 60:
        return 1
    if lines_changed <= 180:
        return 2
    if lines_changed <= 450:
        return 3
    if lines_changed <= 900:
        return 5
    if lines_changed <= 1700:
        return 8
    return 13


def to_points(raw_score: int) -> int:
    for point in POINTS:
        if raw_score <= point:
            return point
    return POINTS[-1]


def estimate_story_points(change: dict) -> tuple[int, list[str], str, int]:
    base = base_story_points(change["lines_changed"])
    risk_steps = 0
    rationale: list[str] = [
        f"base story points from line churn: {change['lines_changed']} -> {base}",
    ]

    if change["files_touched"] >= 8:
        risk_steps += 1
        rationale.append("risk step: files touched >= 8")
    if change["files_touched"] >= 15:
        risk_steps += 1
        rationale.append("risk step: files touched >= 15")
    if len(change["dirs_touched"]) >= 3:
        risk_steps += 1
        rationale.append("risk step: top-level directories touched >= 3")
    if change["max_file_churn"] >= 300:
        risk_steps += 1
        rationale.append("risk step: max single-file churn >= 300")
    if change["binaries_touched"] > 0:
        risk_steps += 1
        rationale.append("risk step: binary files changed")
    if change["mode"] == "proposal":
        risk_steps += 1
        rationale.append("risk step: proposal mode uncertainty")

    suggested = to_points(base + risk_steps)
    confidence = "high" if change["mode"] == "diff" else "medium"
    return suggested, rationale, confidence, risk_steps


def as_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate execution LoE from diff or proposal inputs")
    parser.add_argument("--repo-root", required=True, help="Path to the git repository")
    parser.add_argument("--base-ref", help="Base ref for diff-backed estimation")
    parser.add_argument("--head-ref", default="HEAD", help="Head ref for diff-backed estimation")
    parser.add_argument("--proposed-files", help="Path to newline-delimited proposed file list")
    parser.add_argument(
        "--proposal-lines-changed",
        type=int,
        help="Override estimated line churn in proposal mode",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise EstimationError(f"repo root does not exist or is not a directory: {repo_root}")

    if not (repo_root / ".git").exists():
        raise EstimationError(f"repo root is not a git repository: {repo_root}")

    has_diff_mode = bool(args.base_ref)
    has_proposal_mode = bool(args.proposed_files)

    if has_diff_mode and has_proposal_mode:
        raise EstimationError("choose exactly one mode: diff mode (--base-ref) or proposal mode (--proposed-files)")
    if not has_diff_mode and not has_proposal_mode:
        raise EstimationError("missing mode: provide --base-ref for diff mode or --proposed-files for proposal mode")

    codebase = collect_codebase_metrics(repo_root)

    if has_diff_mode:
        change = collect_diff_change(repo_root, args.base_ref, args.head_ref)
    else:
        proposed_file_path = Path(args.proposed_files).resolve()
        if not proposed_file_path.exists() or not proposed_file_path.is_file():
            raise EstimationError(f"proposed file list does not exist: {proposed_file_path}")
        change = collect_proposal_change(proposed_file_path, args.proposal_lines_changed)

    story_points, rationale, confidence, risk_steps = estimate_story_points(change)
    blast_radius = assess_blast_radius(change)
    decomposition_recommended = (
        story_points >= 8
        or change["files_touched"] >= 18
        or change["lines_changed"] >= 1500
    )
    planning = assess_planning_recommendation(
        change=change,
        story_points=story_points,
        decomposition_recommended=decomposition_recommended,
        blast_radius=blast_radius.to_dict(),
    )

    result = {
        "schemaVersion": "execution-estimation.v4",
        "mode": change["mode"],
        "repoRoot": str(repo_root),
        "codebase": {
            "trackedFiles": codebase.tracked_files,
            "sourceFiles": codebase.source_files,
            "sourceLines": codebase.source_lines,
            "skippedLargeFiles": codebase.skipped_large_files,
            "skippedBinaryFiles": codebase.skipped_binary_files,
        },
        "change": {
            "filesTouched": change["files_touched"],
            "linesAdded": change["lines_added"],
            "linesDeleted": change["lines_deleted"],
            "linesChanged": change["lines_changed"],
            "binariesTouched": change["binaries_touched"],
            "maxSingleFileChurn": change["max_file_churn"],
            "topLevelDirectoriesTouched": change["dirs_touched"],
            "touchedFiles": change["files"],
        },
        "comparison": {
            "trackedFilesTouchedPct": as_percent(change["files_touched"], codebase.tracked_files),
            "sourceLinesChangedPct": as_percent(change["lines_changed"], codebase.source_lines),
        },
        "risk": {
            "blastRadius": blast_radius.to_dict(),
        },
        "planning": planning.to_dict(),
        "estimation": {
            "storyPoints": story_points,
            "confidence": confidence,
            "riskSteps": risk_steps,
            "decompositionRecommended": decomposition_recommended,
            "rationale": rationale,
        },
    }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EstimationError as error:
        print(json.dumps({"error": str(error)}, indent=2, sort_keys=True))
        raise SystemExit(2)
