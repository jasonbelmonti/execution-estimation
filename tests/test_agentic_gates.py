#!/usr/bin/env python3
"""Regression tests for agentic execution gates."""

from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from blast_radius import assess_blast_radius  # noqa: E402
from estimate_execution import (  # noqa: E402
    assess_decomposition,
    collect_diff_change,
    decide_execution,
    estimate_lines_for_path,
    estimate_story_points,
    normalize_paths,
    top_level_dirs,
)
from planning_recommendation import assess_planning_recommendation  # noqa: E402


def git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def proposal_change(paths: list[str], lines_changed: int | None = None) -> dict:
    files = normalize_paths(paths)
    per_file = [estimate_lines_for_path(path) for path in files]
    estimated_lines = sum(per_file) if lines_changed is None else lines_changed
    lines_added = int(round(estimated_lines * 0.6))

    return {
        "mode": "proposal",
        "files": files,
        "files_touched": len(files),
        "lines_added": lines_added,
        "lines_deleted": estimated_lines - lines_added,
        "lines_changed": estimated_lines,
        "binaries_touched": 0,
        "max_file_churn": max(per_file) if per_file else 0,
        "dirs_touched": top_level_dirs(files),
    }


def gate_assessment(paths: list[str], depth: int = 0) -> tuple[object, object, object]:
    change = proposal_change(paths)
    story_points = estimate_story_points(change)
    blast_radius = assess_blast_radius(change)
    decomposition = assess_decomposition(change, story_points.base_story_points, depth)
    planning = assess_planning_recommendation(
        change=change,
        base_story_points=story_points.base_story_points,
        adjusted_story_points=story_points.adjusted_story_points,
        decomposition_recommended=decomposition.recommended,
        blast_radius=blast_radius.to_dict(),
    )
    return story_points, decomposition, planning


class AgenticGateTests(unittest.TestCase):
    def test_proposal_uncertainty_does_not_force_decomposition(self) -> None:
        paths = [f"src/features/foo/file{i}.ts" for i in range(1, 7)]

        story_points, decomposition, planning = gate_assessment(paths)

        self.assertEqual(story_points.base_story_points, 5)
        self.assertEqual(story_points.adjusted_story_points, 8)
        self.assertFalse(decomposition.recommended)
        self.assertFalse(planning.recommended)
        self.assertFalse(planning.blocks_execution)

    def test_single_medium_blast_signal_does_not_block_execution(self) -> None:
        change = proposal_change(["package.json"])
        story_points = estimate_story_points(change)
        blast_radius = assess_blast_radius(change)
        decomposition = assess_decomposition(change, story_points.base_story_points, 0)
        planning = assess_planning_recommendation(
            change=change,
            base_story_points=story_points.base_story_points,
            adjusted_story_points=story_points.adjusted_story_points,
            decomposition_recommended=decomposition.recommended,
            blast_radius=blast_radius.to_dict(),
        )
        execution = decide_execution(decomposition, planning, blast_radius)

        self.assertFalse(decomposition.recommended)
        self.assertFalse(planning.recommended)
        self.assertEqual(planning.level, "none")
        self.assertFalse(planning.blocks_execution)
        self.assertEqual(execution.action, "proceed-with-controls")

    def test_api_and_lib_paths_are_not_boundary_signals_by_name_alone(self) -> None:
        change = proposal_change(["src/api/users.ts", "src/lib/format.ts"])
        blast_radius = assess_blast_radius(change)

        self.assertEqual(blast_radius.level, "low")
        self.assertEqual(blast_radius.signals, ())

    def test_wide_low_impact_proposal_does_not_trigger_planning(self) -> None:
        paths = [f"docs/page{i}.md" for i in range(1, 9)]

        _story_points, decomposition, planning = gate_assessment(paths)

        self.assertFalse(decomposition.recommended)
        self.assertFalse(planning.recommended)
        self.assertFalse(planning.blocks_execution)

    def test_high_blast_radius_blocks_for_required_planning(self) -> None:
        paths = ["src/auth/token.ts", "db/schema.sql"]

        _story_points, decomposition, planning = gate_assessment(paths)

        self.assertFalse(decomposition.recommended)
        self.assertTrue(planning.recommended)
        self.assertEqual(planning.level, "required")
        self.assertTrue(planning.blocks_execution)

    def test_decomposition_depth_suppresses_repeat_child_splits(self) -> None:
        paths = [f"src/features/foo/file{i}.ts" for i in range(1, 13)]

        _story_points, first_pass, _planning = gate_assessment(paths, depth=0)
        _story_points, child_pass, _planning = gate_assessment(paths, depth=1)

        self.assertTrue(first_pass.recommended)
        self.assertFalse(child_pass.recommended)

    def test_include_working_tree_honors_explicit_head_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            git(repo_root, "init")
            git(repo_root, "checkout", "-b", "main")
            git(repo_root, "config", "user.email", "test@example.com")
            git(repo_root, "config", "user.name", "Test User")

            write_text(repo_root / "base.txt", "base\n")
            git(repo_root, "add", ".")
            git(repo_root, "commit", "-m", "base")

            git(repo_root, "checkout", "-b", "requested-head")
            write_text(repo_root / "requested.txt", "requested\n")
            git(repo_root, "add", ".")
            git(repo_root, "commit", "-m", "requested change")

            git(repo_root, "checkout", "main")
            git(repo_root, "checkout", "-b", "current-head")
            write_text(repo_root / "current.txt", "current\n")
            git(repo_root, "add", ".")
            git(repo_root, "commit", "-m", "current change")
            write_text(repo_root / "local.txt", "local\n")

            change = collect_diff_change(repo_root, "main", "requested-head", True)

            self.assertIn("requested.txt", change["files"])
            self.assertIn("local.txt", change["files"])
            self.assertNotIn("current.txt", change["files"])


if __name__ == "__main__":
    unittest.main()
